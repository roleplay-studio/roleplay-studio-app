"""Stub base for future Anthropic-compatible LLM providers (Phase 3).

Anthropic's wire protocol (messages API, ``x-api-key`` header,
``system`` as a top-level field rather than a messages entry) is
incompatible with the OpenAI chat-completions shape that
``BaseOpenAICompatibleLLM`` implements. To keep the architecture open
to Anthropic without rewriting the factory when the first
Anthropic-compatible provider ships, this module provides:

* ``BaseAnthropicLLM`` — a parallel base class whose subclasses will
  implement ``generate_response`` and ``generate_response_stream``
  against Anthropic's messages API. The HTTP / streaming /
  reasoning plumbing will be filled in once a real provider (Anthropic
  SDK, claude.ai proxy, etc.) is wired up; today the methods
  ``raise NotImplementedError`` so callers fail loudly instead of
  silently returning empty strings.
* Same constructor surface as ``BaseOpenAICompatibleLLM`` —
  ``(api_key, base_url, model, settings=None)`` — so the bootstrap
  factory can dispatch on the provider id and
  hand the resolved values straight over.
* Same lifecycle methods (``startup``, ``close``, ``model_name``) —
  the ``LLMPort`` Protocol in ``app.application.ports`` doesn't care
  which wire protocol a provider uses.

Why a SEPARATE base class and not a subclass of
``BaseOpenAICompatibleLLM``: the Anthropic messages API is not a
chat-completions API. Inheriting would mean every Anthropic
provider would have to override ``_build_body`` and the streaming
parser to ship a totally different shape — at which point
inheritance is misleading rather than helpful. Two parallel bases
sharing a Protocol surface is the cleaner expression of "they
satisfy the same port but speak different protocols".
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

from app.infrastructure.llm.base_openai import LLMChunk  # re-used dataclass


class BaseAnthropicLLM:
    """Stub base for Anthropic-compatible providers.

    The constructor mirrors :class:`BaseOpenAICompatibleLLM` so the
    bootstrap factory can stay provider-id-driven:

        BaseAnthropicLLM(
            api_key=...,
            base_url=...,
            model=...,
            settings=settings,  # optional, for app_referer / defaults
        )

    ``generate_response`` and ``generate_response_stream`` raise
    ``NotImplementedError`` until a concrete provider implements
    them. That's deliberate — the alternative (returning empty
    strings) would silently produce broken responses in production.
    """

    def __init__(
        self,
        api_key: str | None,
        base_url: str,
        model: str,
        *,
        app_referer: str = "http://localhost:1420",
        default_temperature: float = 0.7,
        default_max_tokens: int = 4096,
        reasoning_field_names: list[str] | None = None,
        settings: Any = None,
    ) -> None:
        # Settings propagation follows the same lazy pattern as the
        # OpenAI base — explicit kwargs win, otherwise ``settings``
        # supplies the four derived knobs.
        if settings is not None:
            ref = getattr(settings, "app_referer", None)
            if ref is not None:
                app_referer = ref
            t = getattr(settings, "default_temperature", None)
            if t is not None:
                default_temperature = t
            mx = getattr(settings, "default_max_tokens", None)
            if mx is not None:
                default_max_tokens = mx
            names = getattr(settings, "reasoning_field_names", None)
            if names is not None and reasoning_field_names is None:
                reasoning_field_names = list(names)

        if api_key:
            self.api_key: str = api_key
        else:
            # Anthropic's "no key" sentinel uses the same shape as the
            # OpenAI base class so the factory's fingerprint works
            # uniformly.
            self.api_key = "sk-no-...ired"
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.app_referer = app_referer
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        self.reasoning_field_names: list[str] = list(reasoning_field_names or ["thinking"])

    @property
    def model_name(self) -> str:
        return self.model

    async def startup(self) -> None:
        """Lifecycle hook — placeholder until a real provider ships."""

    async def close(self) -> None:
        """Lifecycle hook — placeholder until a real provider ships."""

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Single-turn completion. Stub raises until implemented."""
        raise NotImplementedError(
            f"{type(self).__name__} does not yet implement generate_response — "
            "anthropic-compatible providers are planned but not shipped."
        )

    async def generate_response_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[LLMChunk]:
        """Streaming completion. Stub raises until implemented."""
        raise NotImplementedError(
            f"{type(self).__name__} does not yet implement generate_response_stream — "
            "anthropic-compatible providers are planned but not shipped."
        )

        # Make this an async generator for type-checkers, even though
        # ``raise`` on every entry means the body is unreachable.
        if False:  # pragma: no cover - typing aid only
            yield LLMChunk()
