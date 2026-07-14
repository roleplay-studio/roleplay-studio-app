"""OpenRouter LLM provider — thin subclass of ``BaseOpenAICompatibleLLM``.

Phase 1.3 reference implementation. The HTTP / streaming / reasoning
logic lives in the base; this module wires OpenRouter's defaults
(base URL, default chat model, available-model list) so the
SetupWizard's ``/api/setup/providers`` endpoint can introspect the
provider without a side-registry.

Bootstrapping passes a ``Settings`` instance the same way the
pre-refactor ``OpenRouterLLM(settings=...)`` did — see
``app/bootstrap.py`` — so the legacy ``Settings`` constructor
fallback (``settings=None`` lazy-resolves from env) keeps working for
the historical test fixtures.
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.llm.base_openai import BaseOpenAICompatibleLLM
from app.infrastructure.llm.providers._provider_llm import ProviderCatalog

catalog = ProviderCatalog(
    provider_id="openrouter",
    label="OpenRouter",
    description="Access many models through one API",
    # OpenRouter isOpenAI-compatible at the wire-protocol level.
    default_base_url="https://openrouter.ai/api/v1",
    # ``openai/gpt-4o-mini`` is the cheapest usable flagship the
    # gateway exposes for free-trial tier; the full model list is
    # hundreds of entries (managed by OpenRouter themselves, not by
    # this app). We expose a small curated subset below — the wizard
    # also lets the operator paste a custom id.
    default_model="openai/gpt-4o-mini",
    available_models=(
        "openai/gpt-4o-mini",
        "openai/gpt-4o",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-pro-1.5",
        "meta-llama/llama-3.1-70b-instruct",
    ),
    needs_key=True,
    manual_setup=False,
)


class OpenRouterLLM(BaseOpenAICompatibleLLM):
    """OpenRouter (https://openrouter.ai) — generic OpenAI-compatible.

    Hand-written Phase-1.3 subclass with its own (settings, model)
    constructor — NOT a ``ProviderLLM`` subclass. The reason:
    OpenRouter needs the ``HTTP-Referer`` and ``X-Title`` headers
    wired to settings-aware values for the OpenRouter ranking page,
    which the generic ProviderLLM plumbing doesn't currently model.
    Migration to ProviderLLM stays on the Phase-3.5 roadmap.

    Constructing without a Settings instance falls back to
    ``Settings.from_env()`` to preserve the historical
    ``OpenRouterLLM(api_key="")`` test pattern.
    """

    catalog = catalog  # for /api/setup/providers discovery
    provider_id = "openrouter"

    def __init__(
        self,
        settings: Any | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        if settings is None:
            from app.infrastructure.config import Settings

            settings = Settings.from_env()

        # Resolve the model id: explicit kwarg wins over settings.
        chosen_model = model if model is not None else settings.chat_model

        # Resolve the API key. Bootstrap historically passed ``None``
        # and relied on the base reading ``settings.llm_api_key``; we
        # keep that path. An explicit ``api_key`` kwarg wins (tests).
        if api_key is None:
            secret = getattr(settings, "llm_api_key", None)
            api_key = secret.get_secret_value() if secret is not None else None

        super().__init__(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            model=chosen_model,
            settings=settings,
        )
