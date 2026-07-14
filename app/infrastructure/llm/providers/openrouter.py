"""OpenRouter LLM provider — thin subclass of ``BaseOpenAICompatibleLLM``.

The HTTP / streaming / reasoning logic lives in the base; this
module only wires OpenRouter's defaults (base URL + chat-model).
Bootstrapping passes a ``Settings`` instance the same way the
pre-refactor ``OpenRouterLLM(settings=...)`` did — see
``app/bootstrap.py:80-86`` — so the legacy call-sites keep working
during the Phase 1 refactor and only get rewritten in Phase 3 to
take provider defaults from ``api.constants.PROVIDERS["openrouter"]``.
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.llm.base_openai import BaseOpenAICompatibleLLM


class OpenRouterLLM(BaseOpenAICompatibleLLM):
    """OpenRouter (https://openrouter.ai) — generic OpenAI-compatible.

    Constructor keeps the pre-refactor signature
    ``OpenRouterLLM(settings, model=None)`` so ``app/bootstrap.py``
    doesn't need to change yet. The model id is resolved from the
    override kwarg or the settings-default chain (``fast_model`` →
    ``chat_model``) so the same code drives both the primary LLM
    and the ``fast_llm`` summarizer.
    """

    def __init__(
        self,
        settings: Any | None = None,
        model: str | None = None,
        api_key: str | None = None,
    ) -> None:
        """OpenRouter subclass — keeps the pre-refactor call shape.

        ``settings=None`` is preserved as the legacy fallback: the
        historical ``OpenRouterLLM(api_key="")`` constructor in
        ``tests/test_reasoning_separation`` relied on it. When no
        ``Settings`` is supplied we lazy-resolve it from the env so
        the same default chain (``llm_api_key`` → ``chat_model`` →
        ``llm_base_url``) applies. Tests that want full control can
        pass a Settings fixture; tests that don't care can pass ``None``.
        """
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
