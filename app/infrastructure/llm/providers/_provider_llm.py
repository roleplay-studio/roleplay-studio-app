"""Shared base for per-provider LLM subclasses (Phase 2).

The Phase-1 ``OpenRouterLLM`` subclass is hand-written with hard-coded
``base_url``; the eight remaining OpenAI-compatible providers (openai,
lm-studio, deepseek, gigachat, grok, kimi, minimax, yandexgpt, z-ai)
all follow the same pattern — they don't override any behaviour, they
only declare their default ``base_url`` and chat ``model`` from the
canonical registry in ``api.constants.PROVIDERS``.

To avoid nine near-identical subclasses we add a tiny shared base:
``ProviderLLM`` reads its defaults off a class-level ``provider_id``
attribute and looks them up in ``PROVIDERS`` at construction time.
Each concrete subclass is then a one-liner: ``provider_id = "openai"``.

Why class-level ``provider_id`` and not a runtime kwarg:
* The bootstrap factory (Phase 3) instantiates a class by its import
  path — keeping the id on the class lets the factory
  ``provider_class(provider_id).build(...)`` work without a registry
  dance.
* Grep-ability: ``grep -n "provider_id =" app/infrastructure/llm/providers``
  lists every supported provider with a single line each.

Layering rules:
* ``ProviderLLM`` lives here, NOT in ``base_openai.py``. Per AGENTS.md
  (clean architecture), the base class is provider-agnostic; the
  registry-aware glue is downstream of it.
* This file imports ``api.constants`` at module level. That's fine —
  ``app.infrastructure`` is downstream of ``api`` in our layering, and
  importing ``api.constants`` lazily would add complexity to every
  subclass for no benefit (the cycle that haunts ``app.infrastructure.config``
  does not affect ``api.constants.LANGUAGES`` or ``api.constants.PROVIDERS``).
"""

from __future__ import annotations

from typing import ClassVar

from api.constants import PROVIDERS
from app.infrastructure.llm.base_openai import BaseOpenAICompatibleLLM


class ProviderLLM(BaseOpenAICompatibleLLM):
    """Base for thin per-provider subclasses.

    Subclasses MUST set the class-level ``provider_id`` attribute to a
    key of ``api.constants.PROVIDERS``. All other behaviour comes
    from ``BaseOpenAICompatibleLLM``; subclasses add nothing.

    The constructor accepts the same kwargs as the base and reads
    the per-provider ``default_base_url`` and ``default_model``
    automatically when the caller does not pass them explicitly.
    """

    provider_id: ClassVar[str] = ""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        **kwargs,
    ) -> None:
        if not self.provider_id:
            raise RuntimeError(
                f"{type(self).__name__} must set provider_id — did you forget "
                "the class-level attribute?"
            )
        defaults = PROVIDERS.get(self.provider_id)
        if defaults is None:
            raise RuntimeError(
                f"PROVIDERS has no entry for {self.provider_id!r}; add it in "
                "api/constants.py before shipping this subclass."
            )

        chosen_base_url = base_url or defaults.get("default_base_url", "")
        chosen_model = model or defaults.get("default_model", "")

        if not chosen_base_url:
            # ``custom`` and similar: caller MUST provide base_url; the
            # base_url in PROVIDERS is empty by design.
            raise ValueError(
                f"provider {self.provider_id!r} has no default_base_url in "
                "PROVIDERS — pass base_url= explicitly."
            )
        # ``default_model`` may legitimately be empty (lm-studio's users
        # pick whatever model LM Studio is currently serving); the
        # base class happily passes an empty model id through — the
        # provider is expected to know which model it's talking to.

        super().__init__(
            api_key=api_key,
            base_url=chosen_base_url,
            model=chosen_model,
            **kwargs,
        )
