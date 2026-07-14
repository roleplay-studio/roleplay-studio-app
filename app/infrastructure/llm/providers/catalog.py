"""Provider catalog discovery — single entry point for wizard data.

Both the bootstrap factory and the ``/api/setup/providers`` HTTP
endpoint need a list of every supported LLM provider. Catalog data
used to live in :data:`api.constants.PROVIDERS`, but Phase 1.5 moved
it into per-file :class:`ProviderCatalog` instances so each provider
owns its own metadata (including the per-provider ``available_models``
list, which the wizard now uses to populate its model dropdown).

This module exposes two helpers:

* :func:`all_provider_catalogs` — iterates every concrete subclass
  in ``app.infrastructure.llm.providers`` and yields each one's
  :class:`ProviderCatalog` instance.
* :func:`catalogs_as_wizard_list` — same iteration, flattened to the
  JSON shape the SetupWizard's ``wizardState.Provider`` interface
  consumes (used by ``api/routes/setup.py``'s ``list_providers``).

The discovery goes through ``importlib.iter_modules`` rather than a
hard-coded list so a 11th provider only requires adding one file —
the discovery picks it up automatically. ``MockLLM`` is excluded
because the SetupWizard only lists real network-bearing providers
(the "mock" choice is a CLI-level concern).
"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Iterator

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
)

# Walk every module under the providers package, collect the first
# ProviderCatalog instance we find in each. We use this both for the
# wizard's response and as the registry for the bootstrap factory
# (Phase 3) — so a new provider added with a catalog + subclass is
# automatically visible everywhere without a separate update step.

_PROVIDERS_PACKAGE = "app.infrastructure.llm.providers"


def _iter_provider_modules() -> Iterator[str]:
    """Yield the dotted path of every Python module in the providers pkg."""
    package = importlib.import_module(_PROVIDERS_PACKAGE)
    for module_info in pkgutil.iter_modules(package.__path__):
        if module_info.name.startswith("_"):
            # Internal helpers (the shared base, the discovery module
            # itself) are skipped — they have no catalog.
            continue
        yield f"{_PROVIDERS_PACKAGE}.{module_info.name}"


def all_provider_catalogs() -> list[ProviderCatalog]:
    """Every concrete provider's :class:`ProviderCatalog`, alphabetically.

    ``MockLLM`` is excluded — the wizard lists real, network-bearing
    providers only. The mock simulator is selected through
    ``Settings.llm_provider = 'mock'`` (an env-level escape hatch),
    not through the SetupWizard dropdown.

    Returns duplicates removed (defensive: a module that exposes two
    ``ProviderCatalog`` instances would otherwise leak).
    """
    seen: dict[str, ProviderCatalog] = {}
    for module_name in _iter_provider_modules():
        module = importlib.import_module(module_name)
        for attr_name in dir(module):
            attr = getattr(module, attr_name, None)
            if isinstance(attr, ProviderCatalog):
                if attr.provider_id not in seen:
                    seen[attr.provider_id] = attr
                break  # one catalog per module
    return [seen[k] for k in sorted(seen)]


def catalogs_as_wizard_list() -> list[dict[str, object]]:
    """JSON-serialised view for ``GET /api/setup/providers``.

    The frontend's :class:`wizardState.Provider` interface consumes
    the same shape :data:`api.constants.PROVIDERS` used to emit — so
    ``api/routes/setup.py``'s ``list_providers`` handler can swap to
    this helper without touching the wizard-side code.
    """
    return [cat.to_wizard_dict() for cat in all_provider_catalogs()]


def find_catalog(provider_id: str) -> ProviderCatalog | None:
    """Look up a single catalog by id. Returns ``None`` on miss — the
    bootstrap factory falls back to ``MockLLM`` in that case."""
    for cat in all_provider_catalogs():
        if cat.provider_id == provider_id:
            return cat
    return None
