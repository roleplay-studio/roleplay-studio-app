"""Deterministic in-process LLM simulator for tests and E2E suites.

Why it exists
-------------
``tests/`` and ``frontend/e2e/`` need a real LLM adapter so the entire
streaming pipeline (orchestrator → FastAPI SSE → frontend ``fetch`` →
``ReadableStream`` reader) is exercised against a real wire, but
hitting Deepseek/OpenRouter on every CI run was both expensive
(~$0.001/run but unbounded at scale) and flaky (network rate-limits).
``MockLLM`` swaps in for the duration of a test run via
``LLM_PROVIDER=mock`` (see ``Settings.llm_provider`` and
``bootstrap.build_container``) and emits byte-identical responses so
visual snapshots are stable.

Contract
--------
Implements the same public surface as ``OpenRouterLLM``:

* ``__init__(settings, *, model=None)`` — same kwargs
* ``await llm.startup()`` / ``await llm.close()`` — idempotent, no-op
  (no socket to manage). Pair with the FastAPI lifespan handler just
  like the real LLM.
* ``await generate_response(messages, ...)`` — returns one string
* ``async for chunk in generate_response_stream(messages, ...)`` —
  yields ``LLMChunk`` objects identical in shape to what the real
  provider emits: per-character ``content`` deltas, optional
  ``reasoning`` field, terminal ``usage`` block
* ``llm.model_name`` — the value the dev-mode debug payload reads

Determinism
-----------
The default response is a fixed string ("Hello from the mock LLM.")
followed by an echo of the last user message so multi-turn tests
have something the orchestrator can persist that actually reflects
the conversation. Every chunk goes through ``asyncio.sleep`` with a
constant delay so the SSE wire shape matches what the real provider
sends (timestamped token-by-token deltas), but no randomness is
introduced — visual snapshots are stable across runs.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator

from app.infrastructure.config import Settings
from app.infrastructure.llm import LLMChunk

logger = logging.getLogger(__name__)


#: Default text the mock emits as the assistant turn. Picked to be
#: long enough that streaming is visible (matches Playwright SSE timing
#: helpers in frontend/e2e/lib/sse.ts) but short enough to keep visual
#: snapshots tiny.
DEFAULT_RESPONSE_PREFIX = "Hello from the mock LLM. "

#: Per-character delay when streaming. Large enough that the
#: ``expectStream`` helper in tests/critical/* actually sees multiple
#: ``data:`` events, small enough that the whole turn finishes in
#: well under a second.
_DEFAULT_STREAM_DELAY_S = 0.005


def _last_user_text(messages: list[dict[str, str]]) -> str:
    """Return the content of the last ``role == "user"`` message, or ``""``.

    Used to seed the echo response. The orchestrator may pass many
    internal messages (system, function, etc.); we deliberately ignore
    everything except the most recent user turn.
    """
    for m in reversed(messages):
        if m.get("role") == "user":
            return m.get("content") or ""
    return ""


class MockLLM:
    """LLM adapter that emits deterministic streamed responses.

    Implements the same protocol as ``OpenRouterLLM`` (see ``LLMPort`` in
    ``app.application.ports``) so ``build_container`` can build either
    implementation interchangeably.

    The simulator is intentionally **cooperative on delay** — every
    chunk yields with ``asyncio.sleep(_DEFAULT_STREAM_DELAY_S)``. Tests
    that want fast runs can monkey-patch this attribute on the instance.
    """

    # Sentinel model name the orchestrator's debug modal can render.
    # Distinct from a real model so it is obvious in the UI that the
    # response came from the mock (dev-mode debug modal shows the model
    # used for the request).
    MODEL_NAME = "mock/deterministic-v1"

    def __init__(
        self,
        # ``api_key`` is kept in the signature so the bootstrap path
        # that builds a per-model LLM (for fast_llm) works without an
        # ``isinstance`` branch, but the mock ignores it.
        api_key: str | None = None,
        settings: Settings | None = None,
        model: str | None = None,
    ) -> None:
        self.settings = settings or Settings.from_env()
        self.api_key = ""
        self._model_override = model
        # No socket / no event-loop resources; ``startup``/``close`` are
        # no-ops but kept for symmetry with ``OpenRouterLLM`` so the
        # FastAPI lifespan handler can call them uniformly.
        self._started = False

    async def startup(self) -> None:
        """Idempotent no-op — included for protocol parity with the real LLM.

        The FastAPI lifespan handler (``api/main.py``) calls this for
        every LLM in the container; a no-op keeps the wiring symmetric
        without needing a ``isinstance`` branch.
        """
        self._started = True

    async def close(self) -> None:
        """Idempotent no-op — there is no httpx client to close."""
        self._started = False

    @property
    def model_name(self) -> str:
        """Public alias read by the orchestrator's dev-mode debug payload.

        Distinct from the real chat_model so the dev-mode LLM modal
        makes it obvious the response was served by the simulator.
        """
        return self.MODEL_NAME

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        # ``temperature`` / ``max_tokens`` are accepted for protocol
        # parity with ``OpenRouterLLM.generate_response`` and ignored
        # by the simulator.
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return the deterministic assistant string (no streaming)."""
        return _compose_response(messages)

    async def generate_response_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[LLMChunk]:
        """Yield per-character deltas + a terminal usage block.

        Each yielded ``LLMChunk`` has either a ``content`` or a
        ``reasoning`` field — never both in the same chunk — matching
        ``OpenRouterLLM.generate_response_stream``'s contract. The last
        chunk carries ``usage`` (no visible content) so the dev-mode
        debug modal can render token counts without double-counting
        assistant text.
        """
        text = _compose_response(messages)
        # Emit character-by-character so the SSE wire shape matches a
        # real provider — the Playwright SSE helpers count ``data:``
        # events, not their payload size, so multiple small chunks > one
        # big chunk for those tests.
        for char in text:
            if char:
                yield LLMChunk(content=char)
                # Sleep only after yielding a non-empty chunk to keep
                # deterministic timing. Tests can override
                # ``stream_delay_s`` on the instance to speed this up.
                if self.stream_delay_s > 0:
                    await asyncio.sleep(self.stream_delay_s)
        # Terminal usage chunk — same shape ``_extract_usage`` produces
        # on a real OpenRouter ``data: {...}\n\n`` payload. Tokens are
        # rough estimates; the mock never actually tokenises.
        prompt_tokens = sum(len(m.get("content") or "") for m in messages) // 4
        completion_tokens = len(text) // 4
        yield LLMChunk(
            content="",
            usage={
                "completion_tokens": max(completion_tokens, 1),
                "prompt_tokens": max(prompt_tokens, 1),
                "total_tokens": max(prompt_tokens + completion_tokens, 2),
            },
        )

    #: Per-character stream delay (seconds). Public so tests /
    #: Playwright fixtures can monkey-patch this on the instance to
    #: make the mock finish in <10 ms when they do not care about the
    #: SSE wire timing (e.g. ``make test`` unit suite).
    stream_delay_s: float = _DEFAULT_STREAM_DELAY_S


def _compose_response(messages: list[dict[str, str]]) -> str:
    """Compose the deterministic assistant text.

    Format: ``"Hello from the mock LLM. Echo: <last user text>"``.

    The fixed prefix is enough for visual-snapshot tests to assert on,
    and the echoed user text means multi-turn conversations have a
    response that reflects what was actually said (useful for ``04-state-regenerate``
    and ``02-chat-stream`` critical specs that re-load the thread and
    expect the assistant to have said something specific).
    """
    echo = _last_user_text(messages)
    if not echo:
        return DEFAULT_RESPONSE_PREFIX.strip()
    return f"{DEFAULT_RESPONSE_PREFIX}Echo: {echo!r}."
