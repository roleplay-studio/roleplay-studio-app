"""Direct HTTP LLM client for OpenAI-compatible APIs.

Replaces langchain's ChatOpenAI with a minimal HTTP client that properly
handles quirks of local inference servers like LM Studio:

* Models that emit content in `delta.reasoning_content` instead of
  `delta.content` (common with DeepSeek-based models)
* Models with empty reasoning that still need the response collected
* Any OpenAI-compatible provider: OpenRouter, LM Studio, Ollama, vLLM
"""

import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any

import httpx

from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMChunk:
    """A single piece of a streaming response.

    ``content`` holds the user-visible text. ``reasoning`` holds the
    model's internal chain-of-thought when the provider exposes it
    (DeepSeek, QwQ, o1-style, Claude extended thinking, etc.). At least
    one of the two is non-empty per chunk; the other may be ``None`` or
    ``""``.

    ``usage`` is populated on the terminal chunk when the provider
    emits a usage block (OpenAI / OpenRouter include it as the last
    ``data:`` event before ``[DONE]``). It carries the
    ``prompt_tokens`` / ``completion_tokens`` / ``total_tokens`` triple
    used by the dev-mode LLM debug modal. ``None`` for every other
    chunk, and ``None`` for the whole stream when the provider omits
    usage.

    ``debug_messages`` is a dev-mode side channel: when the orchestrator
    builds the full message list (system + history + RAG + user turn),
    it yields it as the very first chunk of the stream so the upstream
    service can ship it through ``ChatChunk.debug`` to the dev-mode
    modal. ``None`` for every other chunk. Production callers ignore
    it; the SSE route only forwards it when ``Settings.debug_enabled``
    is true.

    Note: ``debug_messages`` is typed as a ``tuple`` (not ``list``) so
    the ``frozen=True`` dataclass actually stays immutable. See M11
    in docs/review.md — a frozen dataclass with ``list`` was an
    illusion of immutability.
    """

    content: str = ""
    reasoning: str | None = None
    usage: dict[str, int] | None = None
    debug_messages: tuple[dict[str, str], ...] | None = None


def _split_delta(
    delta: dict[str, Any],
    reasoning_field_names: list[str] | None = None,
) -> tuple[str, str | None]:
    """Split an OpenAI-style streaming delta into (content, reasoning).

    Crucially, an empty ``content`` does NOT fall back to a
    reasoning field — the previous ``or``-based extraction leaked
    the model's internal thoughts to the user when the API streamed
    an empty content field alongside active reasoning. Reasoning
    is its own field and the frontend decides whether to render it.

    m13: the reasoning field name is now configurable via
    ``Settings.reasoning_field_names`` so operators running
    non-OpenRouter providers (Anthropic ``thinking``, raw DeepSeek
    ``reasoning``, LM Studio ``thought``) can list whichever name
    their model emits. The list is iterated in order; the first
    non-empty value wins. ``None`` falls back to the OpenRouter
    default of ``["reasoning_content"]`` for backward compat.
    """
    content = delta.get("content") or ""
    # m13: try each candidate name in order. Stop at the first hit
    # so a model that emits BOTH ``reasoning`` and ``reasoning_content``
    # prefers the first one in the operator's list (typically the
    # shorter / raw-API name). Note: we use ``is not None`` rather
    # than truthy-check so an empty-string reasoning (the model
    # sent ``"reasoning_content": ""`` to signal "end of reasoning")
    # still resolves to ``""`` rather than ``None``. This matches
    # the pre-m13 behaviour exactly and keeps the existing
    # test_reasoning_separation.py assertions green.
    names = reasoning_field_names or ["reasoning_content"]
    reasoning: str | None = None
    for name in names:
        value = delta.get(name)
        if value is not None:
            reasoning = value
            break
    return content, reasoning


def _extract_usage(chunk: dict[str, Any]) -> dict[str, int] | None:
    """Pull the token-usage block off a streaming chunk, if present.

    OpenAI / OpenRouter emit a final chunk shaped like::

        {"choices": [], "usage": {"prompt_tokens": 42, ...}}

    (empty choices, usage populated) right before ``[DONE]``. Some
    providers also include the model name and a ``prompt_tokens_details``
    sub-dict; we strip those and return only the three scalar counts so
    the frontend has a stable shape to render.
    """
    usage = chunk.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        return {
            "prompt_tokens": int(usage["prompt_tokens"]),
            "completion_tokens": int(usage["completion_tokens"]),
            "total_tokens": int(usage["total_tokens"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


def _extract_finish_reason(choice: dict[str, Any]) -> str | None:
    return choice.get("finish_reason")


def _parse_sse_line(line: str) -> str | None:
    """Parse a single ``data: ...`` SSE line, return the JSON string."""
    line = line.strip()
    if not line.startswith("data: "):
        return None
    payload = line[6:]
    if payload == "[DONE]":
        return None
    return payload


class OpenRouterLLM:
    """LLM adapter implementing the application LLMPort.

    Uses direct HTTP calls instead of langchain to maintain full
    control over request/response handling. Fully async — uses
    httpx.AsyncClient for all operations.

    Lifecycle (K2 fix in docs/review.md):
        llm = OpenRouterLLM(settings)
        await llm.startup()       # creates the httpx.AsyncClient
        ...
        await llm.close()         # explicit cleanup
    """

    def __init__(
        self, api_key: str | None = None, settings: Settings | None = None, model: str | None = None
    ):
        self.settings = settings or Settings.from_env()
        # Resolve the API key from one of three sources, in order:
        # 1) explicit ``api_key`` kwarg (used by tests and the
        #    bootstrap path that builds a per-model LLM with the
        #    fast_model override)
        # 2) ``settings.llm_api_key`` (SecretStr wrapper)
        # 3) empty string → the "no key configured" sentinel
        # The previous ``or ""`` chain worked for plain ``str | None``
        # but a SecretStr is always truthy — we now unwrap explicitly.
        if api_key is not None:
            self.api_key = api_key
        elif self.settings.llm_api_key is not None:
            self.api_key = self.settings.llm_api_key.get_secret_value()
        else:
            self.api_key = ""
        # ``sk-no-...ired`` is the historical "no key set" marker. It
        # never reaches the wire — ``_get_headers`` skips the
        # ``Authorization`` header when api_key == this marker — but
        # the rest of the code can still branch on it. Keeping the
        # sentinel avoids touching those call-sites.
        if not self.api_key:
            self.api_key = "sk-no-...ired"
        self._model_override = model
        # The client is created in ``startup()`` and closed in ``close()``.
        # The previous implementation created it lazily on first call and
        # tried to clean it up in ``__del__`` — but ``__del__`` runs in
        # arbitrary GC contexts, can race with the event loop, and a
        # stored ``_close_task`` formed a reference cycle that prevented
        # GC. See K2 in docs/review.md.
        self._async_client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        """Create the shared httpx.AsyncClient.

        Idempotent — calling it twice is a no-op. Caller is responsible
        for pairing with ``close()`` (typically via FastAPI's lifespan).
        """
        if self._async_client is not None:
            return
        # K7: split timeouts so a slow first byte (read) doesn't share
        # the budget with a hung TCP handshake (connect). The previous
        # ``httpx.AsyncClient(timeout=120.0)`` meant connect=120s — if
        # OpenRouter blinked, the user stared at a frozen spinner for
        # two minutes.
        #
        # K1: explicit httpx.Limits() to cap socket usage. Under
        # parallel SSE streams the default ``max_connections=100`` was
        # technically OK, but ``max_keepalive_connections`` defaults to
        # the same value — every long-lived idle stream held a
        # keepalive socket. We tune it down to 20 keepalives / 100 hard
        # cap, with a 30s expiry to recycle time-waited descriptors.
        self._async_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,  # DNS+TCP+TLS — fail fast
                read=120.0,  # reading the SSE stream can be slow
                write=30.0,
                pool=10.0,  # waiting for a pooled connection
            ),
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0,
            ),
        )

    async def close(self) -> None:
        """Close the httpx client and release sockets. Idempotent."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    def _get_async_client(self) -> httpx.AsyncClient:
        """Return the active client, or raise if ``startup()`` was not called.

        Replaced the previous lazy-create path: that hid lifecycle
        bugs (the client was never closed, and ``__del__``'s attempt
        to close it was unreliable). Callers MUST invoke ``startup()``
        before issuing requests.
        """
        if self._async_client is None:
            raise RuntimeError(
                "OpenRouterLLM client is not initialised — call await llm.startup() first "
                "(typically from the FastAPI lifespan handler in api/main.py)."
            )
        return self._async_client

    @property
    def _base_url(self) -> str:
        return self.settings.llm_base_url.rstrip("/")

    @property
    def _model(self) -> str:
        return self._model_override or self.settings.chat_model

    @property
    def model_name(self) -> str:
        """Public alias of ``_model`` for the application layer.

        The orchestrator's dev-mode debug payload reads this to label
        the model the request was actually served by.
        """
        return self._model

    def _get_headers(self) -> dict[str, str]:
        # m14: HTTP-Referer used to be hard-coded to localhost:1420. It
        # now follows ``Settings.app_referer`` (override via APP_REFERER
        # env var) so production deployments don't leak "this is a
        # Tauri dev box" to OpenRouter's ranking page.
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": self.settings.app_referer,
            "X-Title": "Roleplay Studio",
        }
        api_key = self.api_key
        if api_key and api_key != "sk-no-...ired":
            # M3: never log the key. Previously both ``logger.debug``
            # and ``logger.error(403)`` paths emitted ``self.api_key[:12]``
            # — the prefix is unique enough to identify the provider and
            # if logs leak, the prefix narrows the brute-force keyspace.
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _build_body(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        body = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature
            if temperature is not None
            else self.settings.default_temperature,
            "max_tokens": max_tokens
            if max_tokens is not None
            else self.settings.default_max_tokens,
            "stream": stream,
        }
        return body

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        body = self._build_body(messages, temperature, max_tokens, stream=False)
        url = f"{self._base_url}/chat/completions"
        headers = self._get_headers()
        # M3: log only the fact that a key is configured, never the bytes.
        logger.debug(
            "LLM request: model=%s, key_configured=%s, messages=%d",
            self._model,
            bool(self.api_key) and self.api_key != "sk-no-...ired",
            len(messages),
        )
        client = self._get_async_client()
        resp = await client.post(url, headers=headers, json=body)
        if resp.status_code == 403:
            logger.error(
                "OpenRouter 403 — model=%s, url=%s, body=%s",
                self._model,
                url,
                resp.text[:500],
            )
        resp.raise_for_status()
        data = resp.json()

        choice = data["choices"][0]
        message = choice.get("message", {})

        # CRITICAL: reasoning_content must NEVER leak into the user-visible
        # content. Reasoning models (DeepSeek, QwQ, o1-style) often finish
        # with ``content: null`` and a populated ``reasoning_content``.
        # Using ``or`` to fall back to reasoning previously caused the
        # model's internal chain-of-thought to be persisted as the
        # assistant's response, which then inflated ``short_content``
        # with thoughts. If the model produced no visible content, we
        # return an empty string — the orchestrator/UI can decide what
        # to do (e.g. retry, surface as an error, etc.).
        content = message.get("content") or ""
        return content

    async def generate_response_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[LLMChunk]:
        body = self._build_body(messages, temperature, max_tokens, stream=True)
        url = f"{self._base_url}/chat/completions"
        headers = self._get_headers()

        client = self._get_async_client()
        async with client.stream(
            "POST",
            url,
            headers=headers,
            json=body,
        ) as resp:
            if resp.status_code == 403:
                # M3: don't log the key bytes.
                logger.error(
                    "OpenRouter 403 (stream) — key_configured=%s, model=%s, url=%s",
                    bool(self.api_key) and self.api_key != "sk-no-...ired",
                    self._model,
                    url,
                )
            resp.raise_for_status()
            async for raw_line in resp.aiter_lines():
                payload = _parse_sse_line(raw_line)
                if payload is None:
                    continue

                chunk = json.loads(payload)
                choices = chunk.get("choices", [])
                usage = _extract_usage(chunk)
                for choice in choices:
                    delta = choice.get("delta", {})
                    # m13: pass the configured reasoning field names
                    # from Settings (set via REASONING_FIELD_NAMES env).
                    content, reasoning = _split_delta(delta, self.settings.reasoning_field_names)
                    if content or reasoning:
                        yield LLMChunk(content=content, reasoning=reasoning)
                # Yield a terminal chunk when the provider attaches a usage
                # block to the final event. The frontend uses this to render
                # token counts in the dev-mode LLM debug modal. The chunk
                # has no visible content — only ``usage`` — so it does not
                # double-count the assistant's text.
                if usage is not None and not choices:
                    yield LLMChunk(content="", usage=usage)
