"""M5: built-in bot-type preamble provider.

The default per-bot-type system preambles. The orchestrator constructs
an instance of this class on init when no other ``BotPreambleProvider``
is injected (production, most tests). Per-type overrides come from
``Settings.preamble_overrides`` and are layered on top of the defaults
here.

Why this lives in infrastructure and not domain:
* the *protocol* (``BotPreambleProvider``) is in application/ports.py
  so the orchestrator can be tested with a stub.
* the *default implementation* is here because the strings are
  English UX copy that ships with the binary, not a domain rule.
"""

from __future__ import annotations

from app.domain.enums import BotType

DEFAULT_CHAT_SYSTEM_PROMPT = "You are a helpful assistant."

# Per-type defaults. Kept module-level so they remain easy to grep
# even when the provider is constructed dynamically.
_DEFAULT_PREAMBLES: dict[BotType, str] = {
    BotType.RP: (
        "You are a roleplay character. Stay in character at all times.\n"
        "Use descriptive, immersive language. React to the user's actions and words.\n"
        "Never break character or mention that you are an AI.\n"
    ),
    BotType.ASSISTANT: (
        "You are a helpful assistant.\n"
        "Respond clearly, accurately, and concisely.\n"
        "Use reference material when provided.\n"
    ),
    BotType.AGENT: (
        "You are an AI agent with access to tools.\n"
        "Analyze any uploaded files and use their content to help the user.\n"
        "Respond clearly and accurately.\n"
    ),
}


class BuiltinPreambleProvider:
    """Default ``BotPreambleProvider`` — built-in English preambles.

    ``overrides`` is a ``{bot_type_value: text}`` map (string keys,
    matching the ``BotType`` enum's ``.value``) that wins over the
    built-in defaults. Empty string is a valid override (clears the
    preamble for that type). Pass an empty dict to use defaults.
    """

    def __init__(self, overrides: dict[str, str] | None = None) -> None:
        self._overrides: dict[str, str] = dict(overrides or {})

    def get(self, bot_type: BotType) -> str:
        # Overrides win, then built-in defaults, then the fallback.
        if bot_type.value in self._overrides:
            return self._overrides[bot_type.value]
        return _DEFAULT_PREAMBLES.get(bot_type, DEFAULT_CHAT_SYSTEM_PROMPT)

    def fallback(self) -> str:
        """Used when ``bot_type`` is unknown — same as ``DEFAULT_CHAT_SYSTEM_PROMPT``."""
        return DEFAULT_CHAT_SYSTEM_PROMPT


__all__ = ["DEFAULT_CHAT_SYSTEM_PROMPT", "BuiltinPreambleProvider"]
