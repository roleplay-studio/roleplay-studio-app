"""Shared API constants — languages, upload settings.

Phase 1.5 migration note:

The :data:`PROVIDERS` dictionary used to be the canonical source
of truth for LLM provider metadata (default_base_url, default_model,
needs_key, manual_setup, description, label). Phase 1.5 moved every
piece of that metadata into per-file :class:`ProviderCatalog`
instances under ``app/infrastructure/llm/providers/``.

This module now exposes :data:`PROVIDERS` as a thin derived view
built from the catalogs — every import of
``from api.constants import PROVIDERS`` keeps working, the
``Settings.llm_provider`` validator and the ``ConfigureRequest``
validator both still read the same keys, and the wizard's
``/api/setup/providers`` route gets a uniform list of catalogs.

The catalog is the **single source of truth**; ``PROVIDERS`` here
is a convenience accessor for code that wants the legacy dict
shape (``PROVIDERS[pid]["default_base_url"]`` etc.). New code
should import the catalog discovery directly:

    from app.infrastructure.llm.providers.catalog import (
        all_provider_catalogs,
        find_catalog,
        catalogs_as_wizard_list,
    )
"""

from typing import Any

from app.infrastructure.config import Settings


def _resolve_uploads_dir() -> str:
    return str(Settings.from_env().effective_upload_dir / "avatars")


UPLOADS_DIR = _resolve_uploads_dir()

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


# ── Languages ────────────────────────────────────────────────────────

LANGUAGES: list[dict[str, str]] = [
    {"id": "en", "label": "English"},
    {"id": "ru", "label": "Русский"},
    {"id": "de", "label": "Deutsch"},
    {"id": "fr", "label": "Français"},
    {"id": "ja", "label": "日本語"},
    {"id": "zh", "label": "中文"},
    {"id": "ko", "label": "한국어"},
]


# ── LLM Providers ────────────────────────────────────────────────────
#
# Derived view over the per-file ``ProviderCatalog`` instances. The
# canonical metadata lives in ``app/infrastructure/llm/providers/``;
# this dict is re-built on import and stays in sync because every
# catalog contributes a single entry here.

def _build_providers_view() -> dict[str, dict[str, Any]]:
    """Snapshot every concrete :class:`ProviderCatalog` into the
    legacy ``PROVIDERS`` dict shape.

    Keeps backwards compat with the pre-Phase-1.5 read paths:
    ``Settings.llm_provider`` validator, ``ConfigureRequest``
    validator, the bootstrap factory's comment-only references,
    and a handful of tests.
    """
    from app.infrastructure.llm.providers.catalog import all_provider_catalogs

    out: dict[str, dict[str, Any]] = {}
    for cat in all_provider_catalogs():
        wizard_view = cat.to_wizard_dict()
        out[cat.provider_id] = {
            "label": wizard_view["label"],
            "default_base_url": wizard_view["default_base_url"],
            "default_model": wizard_view["default_model"],
            "needs_key": wizard_view["needs_key"],
            "manual_setup": wizard_view["manual_setup"],
            "description": wizard_view["description"],
        }
    return out


# ``PROVIDERS`` is a frozen snapshot at import time. Tests that mutate
# ``api.constants.PROVIDERS`` directly are no longer supported — the
# source of truth is in the per-file catalogs, where the SetupWizard
# picks up new fields (``available_models``) automatically.
PROVIDERS: dict[str, dict[str, Any]] = _build_providers_view()
