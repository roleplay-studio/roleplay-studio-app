"""Shared base for per-provider LLM subclasses (Phase 2).

The Phase-1 ``OpenRouterLLM`` subclass is hand-written with hard-coded
``base_url``; the eight remaining OpenAI-compatible providers (openai,
lm-studio, deepseek, gigachat, grok, kimi, minimax, yandexgpt, z-ai)
all follow the same pattern — they don't override any behaviour, they
only declare their default ``base_url`` and chat ``model`` from the
canonical registry in ``api.constants.PROVIDERS``.

To avoid nine near-identical subclasses we add a tiny shared base:
``ProviderLLM`` reads its defaults off a class-level ``provider_id``
attribute and the subclass's ``catalog`` (a :class:`ProviderCatalog`
instance declaring all wire-protocol metadata) instead of a global
PROVIDERS dict.

Why class-level ``provider_id`` and not a runtime kwarg:
* The bootstrap factory (Phase 3) instantiates a class by its import
  path — keeping the id on the class lets the factory
  ``provider_class(provider_id).build(...)`` work without a registry
  dance.
* Grep-ability: ``grep -n "provider_id =" app/infrastructure/llm/providers``
  lists every supported provider with a single line each.

* Why per-file ``catalog`` instead of ``api.constants.PROVIDERS``:
  every value that the SetupWizard displays or the bootstrap factory
  reads for a provider lives next to its class. Adding a tenth
  provider only touches two files (provider module + package
  re-export), not three (provider module + re-export + central
  registry). The catalog also carries
  ``available_models: list[str]`` for the wizard's model dropdown —
  a per-provider list that's almost always more useful than a single
  ``default_model`` and that was missing from the central registry.

Layering rules:
* ``ProviderLLM`` lives here, NOT in ``base_openai.py``. Per AGENTS.md
  (clean architecture), the base class is provider-agnostic; the
  registry-aware glue is downstream of it.
* This file imports ``app.application``-level pieces lazily where
  needed. It no longer reads ``api.constants.PROVIDERS`` — that
  import was the V2 of the per-provider
  metadata and Phase-1.5 migrated every value into per-file catalogs.
  (``api.constants.PROVIDERS`` is kept as a thin derived view for
  the few callers that don't import the provider package yet —
  see :func:`build_provider_dict_from_catalogs` in
  ``api/constants.py``.)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from app.infrastructure.llm.base_openai import BaseOpenAICompatibleLLM


@dataclass(frozen=True)
class ProviderCatalog:
    """Per-provider metadata the factory + SetupWizard both consume.

    Frozen so ``cls.catalog`` is stable across the application
    lifetime; ``available_models`` is a tuple for the same reason
    (the M11 lesson — a list in a frozen dataclass is a lie).

    ``available_models`` is the list of model ids an operator can
    pick from a dropdown in the SetupWizard for this provider.
    ``default_model`` is the highlighted item — it MUST also appear
    in ``available_models``, asserted by
    ``tests/test_provider_catalog.py``.
    """

    provider_id: str
    label: str
    description: str
    default_base_url: str
    default_model: str
    available_models: tuple[str, ...]
    needs_key: bool
    manual_setup: bool

    def to_wizard_dict(self) -> dict[str, object]:
        """Serialise for the ``/api/setup/providers`` JSON response.

        The frontend's :class:`SetupWizard.wizardState.Provider`
        interface consumes the same shape the legacy
        ``api.constants.PROVIDERS`` entry used to emit — so the
        wizard-side code stays unchanged while the backend moves
        to per-file catalogs.
        """
        out = {
            "id": self.provider_id,
            "label": self.label,
            "description": self.description,
            "default_base_url": self.default_base_url,
            "default_model": self.default_model,
            "available_models": list(self.available_models),
            "needs_key": self.needs_key,
            "manual_setup": self.manual_setup,
        }
        return out


class ProviderLLM(BaseOpenAICompatibleLLM):
    """Base for thin per-provider subclasses.

    Subclasses MUST set two class-level attributes:

    * ``provider_id`` — the registry key matching
      :class:`ProviderCatalog.provider_id`.
    * ``catalog`` — a :class:`ProviderCatalog` instance carrying the
      default base URL, chat model, available model list, and the
      SetupWizard flags.

    All transport / streaming / reasoning behaviour comes from
    :class:`BaseOpenAICompatibleLLM`.

    The constructor accepts the same kwargs as the base and reads
    the per-provider ``default_base_url`` and ``default_model`` from
    ``cls.catalog`` automatically when the caller does not pass them
    explicitly. ``api.constants.PROVIDERS`` is no longer consulted at
    runtime — every value lives on the class.
    """

    provider_id: ClassVar[str] = ""
    catalog: ClassVar[ProviderCatalog]  # subclasses MUST set this

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
        # The dataclass declares what the wizard + factory need. Don't
        # instantiate without it; that's a programmer error, not a
        # runtime fallback.
        catalog: ProviderCatalog | None = type(self).catalog
        if catalog is None:
            raise RuntimeError(
                f"{type(self).__name__} must set class-level `catalog` — "
                "see ProviderCatalog in app/infrastructure/llm/providers/_provider_llm.py."
            )
        if catalog.provider_id != self.provider_id:
            raise RuntimeError(
                f"{type(self).__name__}.provider_id={self.provider_id!r} does not "
                f"match catalog.provider_id={catalog.provider_id!r}"
            )

        chosen_base_url = base_url or catalog.default_base_url
        chosen_model = model or catalog.default_model

        if not chosen_base_url:
            # ``custom`` and similar: caller MUST provide base_url; the
            # catalog's default_base_url is empty by design.
            raise ValueError(
                f"provider {self.provider_id!r} has no default_base_url in its "
                "catalog — pass base_url= explicitly."
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

