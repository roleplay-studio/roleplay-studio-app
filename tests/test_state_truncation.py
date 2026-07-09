"""Tests for state truncation detection in ChatService.regenerate_state.

Catches the 0.0.4 bug where ``max_tokens=2048`` silently chopped
LLM-generated state mid-section. Downstream reads got syntactically
invalid YAML (unclosed triple-backtick fence, missing key values) and
crashed in subtle ways.

The fix has three parts:

1. ``max_tokens=4096`` — 0.0.4 default was 2048, which is not enough
   for any bot with a rich YAML schema (NPCs with secrets_known
   lists, multi-section world state).
2. **Truncation detection** — we don't get a structured
   ``finish_reason`` back from ``LLMPort.generate_response`` (it
   returns ``str``), so we detect truncation on the way out by
   checking for the closing triple-backtick fence that the bot's
   ``world_state_prompt`` requires. If it's missing, the state was
   chopped mid-section and we flag it.
3. **Marker suffix** — truncated state is suffixed with a
   ``[...truncated]`` line so the UI can detect it and the user
   can hit ``/state/regenerate`` to recover the tail.

Why this matters: state is a 3-layer feature (LLM gen → DB write →
DTO read). The 0.0.4 tests didn't catch the truncation because the
fake LLM returned a fixed string that never hit the cap.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("langgraph", MagicMock())
sys.modules.setdefault("langgraph.graph", MagicMock())
sys.modules.setdefault("langchain_openai", MagicMock())
sys.modules.setdefault("langchain_core", MagicMock())
sys.modules.setdefault("langchain_core.messages", MagicMock())
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_chroma", MagicMock())

from app.application.dto import ConversationRequest  # noqa: E402
from app.application.services.chat import ChatService  # noqa: E402

WORLD_STATE_PROMPT = (
    "You are a world-state tracker. You receive the previous state and "
    "a user message. Respond strictly in YAML inside a fenced code block "
    "(``` at start and end). Do not write anything else."
)


class _FakeBotsRepo:
    def __init__(self, bot):
        self._bot = bot

    async def get(self, bot_id: int):
        return self._bot


class _FakeMessagesRepo:
    def __init__(self):
        self.saved_states: dict[int, str] = {}
        # Use SimpleNamespace so the orchestrator's
        # _load_assistant_content can read ``m.id`` / ``m.content``
        # without us mocking the full MessageDTO surface.
        from types import SimpleNamespace

        self._rows: dict[int, SimpleNamespace] = {}

    async def list_for_thread(self, thread_id, limit=200, before_id=None):
        return list(self._rows.values())

    async def get_previous_assistant_state(self, thread_id, before_message_id=None):
        # Find latest state with id < before_message_id
        candidates = [
            (mid, s)
            for mid, s in self.saved_states.items()
            if before_message_id is None or mid < before_message_id
        ]
        if not candidates:
            return ""
        return max(candidates, key=lambda kv: kv[0])[1]

    async def update_state(self, message_id: int, state: str) -> None:
        self.saved_states[message_id] = state

    def add(self, msg_id: int, content: str) -> None:
        from types import SimpleNamespace

        self._rows[msg_id] = SimpleNamespace(id=msg_id, content=content)


def _make_bot():
    bot = MagicMock()
    bot.id = 1
    bot.world_state_prompt = WORLD_STATE_PROMPT
    bot.dynamic_system_prompt = ""
    return bot


def _make_request(user_input: str = "test"):
    return ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input=user_input,
        bot_name="Lili",
        bot_personality="friendly",
        bot_scenario="",
        first_message="",
        bot_type="rp",
        history=[],
        untrusted_context=[],
        world_state_prompt=WORLD_STATE_PROMPT,
    )


@pytest.mark.asyncio
async def test_well_formed_state_is_saved_untouched() -> None:
    """A state response that closes its fence properly must be
    saved verbatim — no marker, no truncation flag.
    """
    bot = _make_bot()
    bots = _FakeBotsRepo(bot)
    msgs = _FakeMessagesRepo()
    msgs.add(42, "the assistant response")

    class _LLM:
        async def generate_response(self, messages, **kwargs):
            return "```yaml\nuser:\n  health: 90\n```"

    svc = ChatService(bots=bots, messages=msgs, knowledge=None, orchestrator=None, llm=_LLM())
    await svc.regenerate_state(thread_id=1, assistant_message_id=42, bot=bot, request=_make_request())

    saved = msgs.saved_states[42]
    assert saved == "```yaml\nuser:\n  health: 90\n```"
    assert "[...truncated" not in saved


@pytest.mark.asyncio
async def test_unclosed_fence_flags_state_as_truncated() -> None:
    """A response that starts ```yaml but never closes the fence
    is the canonical truncation signature — the LLM hit
    max_tokens mid-section. We must flag it so the UI knows.
    """
    bot = _make_bot()
    bots = _FakeBotsRepo(bot)
    msgs = _FakeMessagesRepo()
    msgs.add(42, "the assistant response")

    class _LLM:
        async def generate_response(self, messages, **kwargs):
            return "```yaml\nuser:\n  health: 90\n  bonds:\n    Lera: 98\n  npc:\n    NPC1:\n      mood: \"angry\"\n      domi"

    svc = ChatService(bots=bots, messages=msgs, knowledge=None, orchestrator=None, llm=_LLM())
    await svc.regenerate_state(thread_id=1, assistant_message_id=42, bot=bot, request=_make_request())

    saved = msgs.saved_states[42]
    assert saved.endswith("\n[...truncated — state gen hit max_tokens]"), (
        f"truncated state must have marker; got: {saved!r}"
    )
    # Original text must be preserved
    assert "```yaml" in saved
    assert "NPC1" in saved


@pytest.mark.asyncio
async def test_freeform_prose_state_is_not_flagged() -> None:
    """If the bot's world_state_prompt does NOT ask for fenced
    output (e.g. asks for free-form prose), we must NOT flag the
    state as truncated when it ends without a fence — that's
    legitimate prose, not a chopped LLM response.
    """
    bot = _make_bot()
    bot.world_state_prompt = "Describe the world state in one paragraph of prose."  # no ```
    bots = _FakeBotsRepo(bot)
    msgs = _FakeMessagesRepo()
    msgs.add(42, "the assistant response")

    class _LLM:
        async def generate_response(self, messages, **kwargs):
            return "The dungeon is dark. The user is afraid."

    svc = ChatService(bots=bots, messages=msgs, knowledge=None, orchestrator=None, llm=_LLM())
    await svc.regenerate_state(thread_id=1, assistant_message_id=42, bot=bot, request=_make_request())

    saved = msgs.saved_states[42]
    assert saved == "The dungeon is dark. The user is afraid."
    assert "[...truncated" not in saved


@pytest.mark.asyncio
async def test_max_tokens_uses_4096_not_2048() -> None:
    """Regression guard: 0.0.4 used ``max_tokens=2048``, which is
    too small for bots with rich YAML schemas (NPCs with
    secrets_known lists, multi-section world state). The fix
    bumped it to 4096 — this test pins that the request carries
    the higher value so a future refactor can't quietly drop it
    back down.
    """
    bot = _make_bot()
    bots = _FakeBotsRepo(bot)
    msgs = _FakeMessagesRepo()
    msgs.add(42, "the assistant response")

    captured: dict = {}

    class _LLM:
        async def generate_response(self, messages, **kwargs):
            captured["max_tokens"] = kwargs.get("max_tokens")
            return "```yaml\nuser:\n  health: 90\n```"

    svc = ChatService(bots=bots, messages=msgs, knowledge=None, orchestrator=None, llm=_LLM())
    await svc.regenerate_state(thread_id=1, assistant_message_id=42, bot=bot, request=_make_request())

    assert captured.get("max_tokens") == 4096, (
        f"regenerate_state must request max_tokens=4096 to avoid silent "
        f"truncation of rich YAML schemas; got {captured.get('max_tokens')!r}"
    )
