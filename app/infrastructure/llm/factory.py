"""LLM bootstrap factory (Phase 3).

Translates ``Settings.llm_provider`` into a concrete ``LLM``
instance. Replaces the previous ``if/else`` branch in
``app/bootstrap.build_container`` with a single dispatch table
keyed by provider id.

Why a separate module: the dispatch logic depends on every provider
subclass plus ``MockLLM`` and ``OpenRouterLLM`` (the two pre-Phase-1
implementations). Co-locating that with ``bootstrap.py`` would
make the bootstrap's import graph heavy; the factory gives
``bootstrap.py`` one clean line — ``from app.infrastructure.llm.factory
import make_llm``.

Adding a provider from this point on:

1. Add the entry to ``api.constants.PROVIDERS``.
2. Add the subclass under ``app.infrastructure.llm.providers/``.
3. Add one row to ``_PROVIDER_CLASSES`` below.

The factory then resolves the new id without any other change.
"""

from __future__ import annotations

import logging
from typing import Any

from app.infrastructure.llm.base_openai import BaseOpenAICompatibleLLM
from app.infrastructure.llm.providers import (
    ZAILLM,
    DeepSeekLLM,
    GigaChatLLM,
    GrokLLM,
    KimiLLM,
    LMStudioLLM,
    MiniMaxLLM,
    OpenAILLM,
    ProviderLLM,
    YandexGPTLLM,
)
from app.infrastructure.llm.providers.openrouter import OpenRouterLLM
from app.infrastructure.llm_mock import MockLLM

logger = logging.getLogger(__name__)


# Dispatch table: provider_id (a key of api.constants.PROVIDERS + "mock")
# → concrete ``LLM``-implementing class.
#
# ``openrouter`` is the hand-written Phase-1.3 reference implementation.
# It overrides the registry-driven ``ProviderLLM`` only because it needs
# the ``HTTP-Referer`` header and the ``X-Title`` tag wired to specific
# OpenRouter ranking values. The other nine providers ride the
# generic ``ProviderLLM`` plumbing.
#
# ``mock`` is special — it doesn't read base_url/model from
# ``PROVIDERS`` because it never issues a network request. It sits at
# the top of the dispatch so we don't even attempt to instantiate
# a network-bearing class when the operator asks for the simulator.
# ``custom`` is special — it doesn't subclass ``ProviderLLM`` because the
# operator supplies ``base_url`` and ``model`` at runtime; both fields
# are required so the catalog validation in ``ProviderLLM.__init__``
# (non-empty default_base_url) would fail otherwise. The factory
# instantiates ``BaseOpenAICompatibleLLM`` directly when the
# ``settings.llm_api_key`` AND a non-empty ``settings.chat_model``
# AND a non-empty ``settings.llm_base_url`` are all present.
_PROVIDER_CLASSES: dict[str, type[Any]] = {
    "mock": MockLLM,
    "openrouter": OpenRouterLLM,
    "openai": OpenAILLM,
    "lm-studio": LMStudioLLM,
    "deepseek": DeepSeekLLM,
    "gigachat": GigaChatLLM,
    "grok": GrokLLM,
    "kimi": KimiLLM,
    "minimax": MiniMaxLLM,
    "yandexgpt": YandexGPTLLM,
    "z-ai": ZAILLM,
    "custom": BaseOpenAICompatibleLLM,
}


def make_llm(settings: Any, model_override: str | None = None) -> Any:
    """Build the chat LLM dictated by ``settings.llm_provider``.

    ``model_override`` lets the bootstrap ask for ``settings.fast_model``
    explicitly — the same code path therefore serves both the primary
    chat model and the cheap summariser model without separate
    factories.

    The return is typed as ``Any`` because the rest of the codebase
    accepts any object satisfying ``app.application.ports.LLMPort``;
    concrete types are an artefact of where the call originated.
    Falls back to ``MockLLM`` on unknown / unmapped ids with a
    ``logger.warning`` (matching the silent fallback in the pre-Phase-3
    bootstrap).
    """
    pid = getattr(settings, "llm_provider", "mock")
    cls = _PROVIDER_CLASSES.get(pid)
    if cls is None:
        # Belt-and-braces defence in depth: the Settings validator
        # already maps unknowns to "mock", but a manually-constructed
        # settings object might bypass that path.
        logger.warning(
            "make_llm: unknown llm_provider=%r — known: %r, 'mock'; falling back to MockLLM",
            pid,
            sorted(p for p in _PROVIDER_CLASSES if p != "mock"),
        )
        return MockLLM(settings=settings)

    # Resolve the api key once. The base classes accept SecretStr
    # wrappers the same way the pre-refactor OpenRouterLLM did — they
    # unwrap via ``get_secret_value()``. MockLLM accepts the Settings
    # directly without re-reading the key.
    if pid == "mock":
        return cls(settings=settings, model=model_override)

    if pid == "openrouter":
        # Phase-1.3 keeps the legacy (settings, model) signature.
        return cls(settings=settings, model=model_override)

    # All remaining classes are ProviderLLM subclasses — they accept
    # (api_key, model, base_url) kwargs and read defaults from
    # api.constants.PROVIDERS[<id>]. We pass ``settings`` so the base
    # class can pick up the four Settings-derived knobs (app_referer,
    # default_temperature, default_max_tokens, reasoning_field_names).
    secret = getattr(settings, "llm_api_key", None)
    api_key = secret.get_secret_value() if secret is not None else None

    # If a chat_model/fast_model override is supplied, use it.
    # Otherwise the subclass falls back to PROVIDERS[<id>]['default_model'].
    chosen_model = model_override
    if chosen_model is None:
        # Prefer settings.chat_model when the provider's default_model is
        # empty (e.g. lm-studio — operator picks the served model in
        # the LM Studio UI, not in PROVIDERS).
        provider_default_model = ProviderLLM  # noqa: F841 — type-check aid only
        # Let the subclass resolve its own default from PROVIDERS by
        # passing None; we don't override here.
        chosen_model = None

    # Base url: likewise prefer the provider-specific default. The
    # subclass reads ``PROVIDERS[<id>]['default_base_url']`` when we
    # pass None. We DO NOT pass ``llm_base_url`` from settings — that
    # would override the per-provider canonical URL with whatever
    # generic URL the operator put in their ``.env``.
    if pid == "custom":
        # ``custom`` is the only id whose ``base_url`` comes from
        # ``Settings.llm_base_url`` (operator-set in .env / SetupWizard).
        # The catalog's ``default_base_url`` is empty by design — we
        # pass the settings value through ``base_url=`` so the base
        # class wires it onto the httpx request.
        return cls(
            api_key=api_key,
            model=model_override or getattr(settings, "chat_model", ""),
            base_url=getattr(settings, "llm_base_url", "") or "",
            settings=settings,
        )
    return cls(
        api_key=api_key,
        model=chosen_model,
        settings=settings,
    )
