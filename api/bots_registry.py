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


def _examples_dir() -> Path:
    """Resolve the bots_examples dir for the current runtime.

    * Dev: project root (``/Users/.../streamlit-llm-roleplay/bots_examples/``)
    * Frozen (PyInstaller): inside the ``_MEIPASS`` extraction dir
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    else:
        # api/bots_registry.py → project root is two parents up
        base = Path(__file__).resolve().parent.parent
    return base / _STARTER_DIR_NAME


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
    examples_dir = _examples_dir()
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
