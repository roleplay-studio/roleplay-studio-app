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

from format_standart_rp import fix_markdown


class FormatStandartRpRepairer:
    """Default ``MarkdownRepairer`` backed by the
    ``format-standart-rp`` library."""

    def repair(self, text: str, mode: str = "close") -> str:
        """See ``MarkdownRepairer.repair`` in ports.py.

        ``fix_markdown`` raises ``ValueError`` on unknown modes;
        we let that propagate so the caller (the chat service)
        fails fast instead of silently treating the typo as
        ``"close"``.
        """
        return fix_markdown(text, fix_unclosed=mode)
