"""Discover and list starter bots shipped in ``bots_examples/``.

Walks the project-bundled ``bots_examples/`` directory (works in both dev and
PyInstaller-frozen modes), parses each ``.json`` / ``.png`` via
:mod:`api.bot_loader`, and produces a JSON-serialisable list of bot cards
ready for the setup wizard.

For ``.png`` cards the raw file bytes double as the bot's avatar and are
returned as a ``data:image/png;base64,...`` URL — same convention the rest of
the project uses for inline previews. For ``.json`` cards there's no embedded
image, so we fall back to the deterministic gradient placeholder already used
by the character-card export pipeline.
"""

from __future__ import annotations

import base64
import logging
import sys
from pathlib import Path

from api.bot_loader import load_from_json, load_from_png
from app.infrastructure.character_card_extras import generate_placeholder_png

logger = logging.getLogger(__name__)

_STARTER_DIR_NAME = "bots_examples"
_SUPPORTED_EXTS = {".json", ".png"}


def _bundled_examples_dir() -> Path:
    """Bundled starter-bots folder shipped with the project.

    Used as a fallback when ``<ROLEPLAY_DATA_DIR>/bots_examples`` is
    missing or empty, so the setup wizard never shows an empty list
    after a fresh install.

    * Frozen (PyInstaller): inside the ``_MEIPASS`` extraction dir
      so the bundle ships pre-cooked.
    * Dev: ``<project_root>/bots_examples`` (one parent up from
      ``api/``). Anything that lives next to ``pyproject.toml`` is
      reachable this way.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    else:
        # api/bots_registry.py → project root is one parent up
        base = Path(__file__).resolve().parent.parent
    return base / _STARTER_DIR_NAME


def _candidates() -> list[Path]:
    """Return the candidate starter-bots directories in priority order.

    The first directory that contains at least one supported card
    (``*.json`` / ``*.png``) wins; later entries are tried only when
    the earlier ones are missing or empty. This keeps the user-facing
    experience deterministic:

    * User-defined data (``STARTER_BOTS_DIR`` or
      ``<ROLEPLAY_DATA_DIR>/bots_examples``) always takes precedence
      when present.
    * The bundled set is a safety net for fresh installs where the
      data dir has no bots yet.

    Order:

    1. ``STARTER_BOTS_DIR`` (absolute path, or relative to the
       data dir when one is set) — explicit per-deployment override.
    2. ``<ROLEPLAY_DATA_DIR>/bots_examples`` — so a single
       ``ROLEPLAY_DATA_DIR=demo`` env var covers DB, chroma, uploads,
       AND starter bots.
    3. Bundled (project root or ``_MEIPASS``).
    """
    import os

    candidates: list[Path] = []

    explicit = os.environ.get("STARTER_BOTS_DIR")
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            data_dir = os.environ.get("ROLEPLAY_DATA_DIR")
            if data_dir:
                p = Path(data_dir) / p
        candidates.append(p)

    data_dir = os.environ.get("ROLEPLAY_DATA_DIR")
    if data_dir:
        candidates.append(Path(data_dir) / _STARTER_DIR_NAME)

    candidates.append(_bundled_examples_dir())
    return candidates


def _has_supported_cards(directory: Path) -> bool:
    """True when ``directory`` contains at least one ``.json``/``.png`` card."""
    if not directory.is_dir():
        return False
    for path in directory.iterdir():
        if path.suffix.lower() in _SUPPORTED_EXTS:
            return True
    return False


def _resolve_examples_dir() -> Path:
    """Pick the first non-empty candidate, or the last one if all are empty.

    Returning the bundled (last) path on total miss keeps the wizard's
    "no starter bots" rendering consistent regardless of which
    directories exist.
    """
    candidates = _candidates()
    for directory in candidates[:-1]:
        if _has_supported_cards(directory):
            return directory
    return candidates[-1]


def _placeholder_avatar_data_url(name: str) -> str:
    """Build a base64 data URL for a deterministic gradient avatar."""
    png = generate_placeholder_png(name)
    return "data:image/png;base64," + base64.b64encode(png).decode("ascii")


def list_starter_bots() -> list[dict]:
    """Return a list of starter-bot cards, sorted by name.

    Each entry: ``{"id", "name", "first_message", "scenario", "personality",
    "categories", "format", "avatar_data_url", "error"}``.

    ``id`` is the on-disk filename stem (e.g. ``puro``), stable across reloads.
    Bots that fail to parse are still listed with ``error`` set so the wizard
    can show the user a warning instead of silently hiding a broken card.
    """
    examples_dir = _resolve_examples_dir()
    if not examples_dir.is_dir():
        return []

    out: list[dict] = []
    for path in sorted(examples_dir.iterdir()):
        if path.suffix.lower() not in _SUPPORTED_EXTS:
            continue

        stem = path.stem
        fmt = path.suffix.lower().lstrip(".")
        # Per-format loader; fall back to a "broken" card on any error.
        try:
            if fmt == "png":
                card = load_from_png(path)
                raw = path.read_bytes()
                avatar_data_url = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
            else:
                card = load_from_json(path)
                avatar_data_url = _placeholder_avatar_data_url(card["name"])
        except (OSError, ValueError) as e:
            logger.warning("Skipping starter bot %s: %s", path, e)
            out.append(
                {
                    "id": stem,
                    "name": stem,
                    "format": fmt,
                    "avatar_data_url": _placeholder_avatar_data_url(stem),
                    "error": str(e),
                    "first_message": "",
                    "scenario": "",
                    "personality": "",
                    "categories": [],
                }
            )
            continue

        out.append(
            {
                "id": stem,
                "name": card["name"],
                "first_message": card.get("first_message", ""),
                "scenario": card.get("scenario", ""),
                "personality": card.get("personality", ""),
                "categories": list(card.get("categories", []) or []),
                "format": fmt,
                "avatar_data_url": avatar_data_url,
            }
        )

    out.sort(key=lambda c: c["name"].lower())
    return out
