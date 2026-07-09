"""Adapter from the ``format-standart-rp`` library to the
``MarkdownRepairer`` port.

The library is intentionally pulled in only at the infrastructure
layer — ``app.application.*`` modules depend on the
``MarkdownRepairer`` Protocol in ``ports.py`` and never on this
module or on ``format_standart_rp`` directly. That keeps the
service layer testable with a stub and lets us swap
implementations later.

For a no-op fallback (used by tests that don't exercise the
markdown-repair code path), see ``_NullMarkdownRepairer`` in
``app/application/services/chat.py``.
"""

from __future__ import annotations

from format_standart_rp import format_roleplay


class FormatStandartRpRepairer:
    """Adapter around the external ``format_standart_rp`` library.

    Wraps ``format_roleplay`` (the roleplay-style prose repairer).
    The library's other helper, ``fix_markdown``, is the close-or-
    strip function used by older code paths; we use
    ``format_roleplay`` here because it applies a prose-style
    transformation that fits the roleplay chat use-case better
    (it normalises asterisks around actions and quotation marks
    around speech).
    """

    def repair(self, text: str, mode: str = "close") -> str:
        return format_roleplay(text)
