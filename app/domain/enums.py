"""Domain enums for Roleplay Studio."""

from __future__ import annotations

from enum import StrEnum


class BotType(StrEnum):
    """Type of a bot — determines conversation prompt structure and UI."""

    RP = "rp"
    ASSISTANT = "assistant"
    AGENT = "agent"

    # Note: ``label`` / ``description`` properties were removed in
    # response to code review #2 (CSV export from a previous tool).
    # The frontend renders BotType labels and descriptions from its
    # own ``BOT_TYPES`` constant in src/lib/api.ts, which keeps the
    # copy under i18n control without round-tripping through the
    # backend. If you need server-side label rendering in the
    # future, add an i18n-aware formatter in
    # ``app.application.formatters`` rather than re-introducing
    # English-only labels here.
