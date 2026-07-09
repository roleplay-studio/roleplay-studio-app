"""Tests for the RP-only gate on state-tracking and dynamic system
prompt features.

State-update and ``dynamic_system_prompt`` are roleplay features by
design. Assistant/agent bots are productivity tools that don't have
a "world" to track and don't benefit from a floating reminder — for
them, the LLM call to derive state is pure token waste, and pushing
``[Reminder]`` / ``[World state]`` blocks into a non-RP context
risks confusing the model and leaking bot author prompts into a
productivity tool where they don't belong.

The gate has to work at three layers (defence in depth):

1. **Auto-spawn in ``stream_message``** — the fire-and-forget
   ``_maybe_run_state_update`` must not be called for non-RP bots.
2. **``ConversationRequest`` construction in ``_build_request``** —
   ``dynamic_system_prompt`` and ``world_state_prompt`` and
   ``prev_world_state`` must be empty for non-RP bots so the
   orchestrator's ``_build_all_messages`` and ``_node_user_input``
   skip the injection.
3. **``regenerate_state`` body** — if the public
   ``POST /state/regenerate`` endpoint is called against a non-RP
   bot, the call must early-return and not burn an LLM call or
   overwrite ``Conversation.state`` with junk.

The 0.0.4 release had a regression where only the world-state
prompt's non-emptiness gated the spawn — meaning a misconfigured
assistant bot with a stray ``world_state_prompt`` would still
trigger the state LLM call. The 0.0.5 fix adds the bot_type check.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.modules.setdefault("langgraph", MagicMock())
sys.modules.setdefault("langgraph.graph", MagicMock())
sys.modules.setdefault("langchain_openai", MagicMock())
sys.modules.setdefault("langchain_core", MagicMock())
sys.modules.setdefault("langchain_core.messages", MagicMock())
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_chroma", MagicMock())

from app.application.dto import (  # noqa: E402
    ConversationRequest,
    MessageDTO,
    SendMessageCommand,
)
from app.application.services.chat import ChatService  # noqa: E402

# ── Helpers ──────────────────────────────────────────────────────────


def _make_bot(bot_type):
    """Return a minimal bot stub the chat service accepts.

    ``bot_type`` is the field the production SQLModel exposes;
    tests that build ``SimpleNamespace`` bots pass it as a string
    (``"rp"`` / ``"assistant"`` / ``"agent"``) and the chat
    service's gating code normalises to ``BotType`` on the way
    through.
    """
    return SimpleNamespace(
        id=1,
        name="Test",
        personality="",
        scenario="",
        first_message="",
        mes_example="",
        world_state_prompt="emit yaml in ```yaml``` block",
        dynamic_system_prompt="stay in character",
        bot_type=bot_type,
    )


class _CaptureLLM:
    """LLM stub that records every call. Used to assert the state
    LLM was NOT called for a non-RP bot.
    """

    def __init__(self):
        self.calls: list[dict] = []

    async def generate_response(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return "```yaml\nuser:\n  health: 90\n```"


class _NoOpMessagesRepo:
    """Minimal repo stub. Records saves so the test can assert
    which fields were stamped and which were zeroed out.
    """

    def __init__(self):
        self.saved: list[dict] = []
        self.update_state_calls: list[tuple[int, str]] = []
        self._rows: dict[int, SimpleNamespace] = {}

    async def save(self, thread_id, role, content, **kwargs):
        self.saved.append({"thread_id": thread_id, "role": role, "content": content, **kwargs})
        return len(self.saved) + 1000

    async def update_state(self, message_id, state):
        self.update_state_calls.append((message_id, state))

    async def list_for_thread(self, thread_id, limit=200, before_id=None):
        return list(self._rows.values())

    async def get_previous_assistant_state(self, thread_id, before_message_id=None):
        return ""


class _NoOpBotsRepo:
    def __init__(self, bot):
        self._bot = bot

    async def get(self, bot_id):
        return self._bot


# ── 1. Auto-spawn gate ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_state_update_auto_spawn_skipped_for_assistant_bot() -> None:
    """The fire-and-forget ``_maybe_run_state_update`` must not be
    called when the bot is an assistant/agent. Spawning it would
    burn an LLM call and write a junk world-state snapshot to
    the DB.
    """
    bot = _make_bot("assistant")
    msgs = _NoOpMessagesRepo()
    llm = _CaptureLLM()

    svc = ChatService(
        bots=_NoOpBotsRepo(bot),
        messages=msgs,
        knowledge=None,
        orchestrator=None,
        llm=llm,
    )

    # Drive the spawn point directly. ``stream_message`` does
    # many things before getting here; calling the wrapper
    # directly with the right args is enough to test the gate.
    from app.application.dto import ConversationRequest

    request = ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        bot_name=bot.name,
        bot_personality="",
        bot_scenario="",
        first_message="",
        bot_type="assistant",
        history=[],
        untrusted_context=[],
        world_state_prompt=bot.world_state_prompt,
        dynamic_system_prompt=bot.dynamic_system_prompt,
    )

    await svc._maybe_run_state_update(
        thread_id=1,
        assistant_message_id=42,
        bot=bot,
        request=request,
    )

    # ``update_state`` must not have been called for an
    # assistant bot — the LLM should never even have run.
    assert llm.calls == [], (
        f"state LLM was called for assistant bot: {llm.calls!r}"
    )
    assert msgs.update_state_calls == [], (
        f"update_state was called for assistant bot: {msgs.update_state_calls!r}"
    )


@pytest.mark.asyncio
async def test_state_update_auto_spawn_skipped_for_agent_bot() -> None:
    bot = _make_bot("agent")
    msgs = _NoOpMessagesRepo()
    llm = _CaptureLLM()

    svc = ChatService(
        bots=_NoOpBotsRepo(bot),
        messages=msgs,
        knowledge=None,
        orchestrator=None,
        llm=llm,
    )

    from app.application.dto import ConversationRequest

    request = ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        bot_name=bot.name,
        bot_personality="",
        bot_scenario="",
        first_message="",
        bot_type="agent",
        history=[],
        untrusted_context=[],
        world_state_prompt=bot.world_state_prompt,
        dynamic_system_prompt=bot.dynamic_system_prompt,
    )

    await svc._maybe_run_state_update(
        thread_id=1,
        assistant_message_id=42,
        bot=bot,
        request=request,
    )

    assert llm.calls == []
    assert msgs.update_state_calls == []


# ── 2. ConversationRequest projection gate ──────────────────────────


@pytest.mark.asyncio
async def test_build_request_zeroes_rp_fields_for_assistant_bot() -> None:
    """``_build_request`` must zero out ``dynamic_system_prompt``,
    ``world_state_prompt``, and ``prev_world_state`` for
    assistant/agent bots. Otherwise the orchestrator's
    ``_build_all_messages`` and ``_node_user_input`` will inject
    a ``[Reminder]`` / ``[World state]`` block into a
    non-RP context.
    """
    bot = _make_bot("assistant")
    bots = _NoOpBotsRepo(bot)
    msgs = _NoOpMessagesRepo()

    svc = ChatService(bots=bots, messages=msgs, knowledge=None, orchestrator=None)

    command = SendMessageCommand(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        file_ids=[],
        persona_id=None,
    )

    # Build a synthetic history with a non-empty state on the
    # previous assistant turn. Even with that, the request must
    # not carry it forward for an assistant bot.
    history = [
        MessageDTO(
            id=99,
            role="assistant",
            content="earlier reply",
            state="```yaml\nold: 1\n```",
        )
    ]

    svc._load_full_history = AsyncMock(return_value=history)
    svc._personas = None
    svc._summarizer = None
    svc._settings = MagicMock(
        default_max_tokens=4096,
        default_temperature=1.0,
        context_compression_enabled=False,
        context_compression_threshold=999,
        context_compression_keep_recent=10,
    )
    # Stub knowledge/RAG search so we don't pull in Chroma. Return
    # an empty hit list — the test is about RP-only fields, not RAG.
    svc._knowledge = AsyncMock(search=AsyncMock(return_value=[]))

    request = await svc._build_request(command)

    # RP-only fields must be zeroed
    assert request.dynamic_system_prompt == "", (
        f"dynamic_system_prompt leaked for assistant bot: {request.dynamic_system_prompt!r}"
    )
    assert request.world_state_prompt == "", (
        f"world_state_prompt leaked for assistant bot: {request.world_state_prompt!r}"
    )
    assert request.prev_world_state == "", (
        f"prev_world_state leaked for assistant bot: {request.prev_world_state!r}"
    )
    assert request.bot_type == "assistant"


@pytest.mark.asyncio
async def test_build_request_keeps_rp_fields_for_rp_bot() -> None:
    """Sanity check: the same path for an RP bot must keep the
    RP-only fields. The gate must not over-zero for legitimate
    RP traffic.
    """
    bot = _make_bot("rp")
    bots = _NoOpBotsRepo(bot)
    msgs = _NoOpMessagesRepo()

    svc = ChatService(bots=bots, messages=msgs, knowledge=None, orchestrator=None)

    command = SendMessageCommand(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        file_ids=[],
        persona_id=None,
    )

    prev_msg = MessageDTO(
        id=99, role="assistant", content="earlier reply", state="```yaml\nold: 1\n```"
    )
    history = [prev_msg]

    svc._load_full_history = AsyncMock(return_value=history)
    svc._personas = None
    svc._summarizer = None
    svc._settings = MagicMock(
        default_max_tokens=4096,
        default_temperature=1.0,
        context_compression_enabled=False,
        context_compression_threshold=999,
        context_compression_keep_recent=10,
    )
    # Stub knowledge/RAG search so we don't pull in Chroma. Return
    # an empty hit list — the test is about RP-only fields, not RAG.
    svc._knowledge = AsyncMock(search=AsyncMock(return_value=[]))

    request = await svc._build_request(command)

    # RP fields must be preserved
    assert request.dynamic_system_prompt == "stay in character"
    assert request.world_state_prompt == "emit yaml in ```yaml``` block"
    assert request.prev_world_state == "```yaml\nold: 1\n```"
    assert request.bot_type == "rp"


# ── 3. regenerate_state gate (defence in depth) ─────────────────────


@pytest.mark.asyncio
async def test_regenerate_state_early_returns_for_non_rp_bot() -> None:
    """``regenerate_state`` is reachable from the public
    ``POST /state/regenerate`` endpoint. A misconfigured call
    against a non-RP bot must early-return, not burn an LLM
    call, and not overwrite ``Conversation.state`` with junk.
    """
    bot = _make_bot("assistant")
    bots = _NoOpBotsRepo(bot)
    msgs = _NoOpMessagesRepo()
    msgs._rows[42] = SimpleNamespace(id=42, content="some assistant text")
    llm = _CaptureLLM()

    svc = ChatService(
        bots=bots, messages=msgs, knowledge=None, orchestrator=None, llm=llm
    )

    request = ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        bot_name=bot.name,
        bot_personality="",
        bot_scenario="",
        first_message="",
        bot_type="assistant",
        history=[],
        untrusted_context=[],
        world_state_prompt=bot.world_state_prompt,
        dynamic_system_prompt=bot.dynamic_system_prompt,
    )

    # Should silently return — no LLM call, no state write.
    await svc.regenerate_state(
        thread_id=1,
        assistant_message_id=42,
        bot=bot,
        request=request,
    )

    assert llm.calls == [], (
        f"regenerate_state must not call LLM for non-RP bot; got {llm.calls!r}"
    )
    assert msgs.update_state_calls == [], (
        f"regenerate_state must not write state for non-RP bot; "
        f"got {msgs.update_state_calls!r}"
    )


@pytest.mark.asyncio
async def test_regenerate_state_runs_for_rp_bot() -> None:
    """Sanity check: same path for an RP bot must actually run
    the LLM call and write state.
    """
    bot = _make_bot("rp")
    bots = _NoOpBotsRepo(bot)
    msgs = _NoOpMessagesRepo()
    msgs._rows[42] = SimpleNamespace(id=42, content="some assistant text")
    llm = _CaptureLLM()

    svc = ChatService(
        bots=bots, messages=msgs, knowledge=None, orchestrator=None, llm=llm
    )

    request = ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        bot_name=bot.name,
        bot_personality="",
        bot_scenario="",
        first_message="",
        bot_type="rp",
        history=[],
        untrusted_context=[],
        world_state_prompt=bot.world_state_prompt,
        dynamic_system_prompt=bot.dynamic_system_prompt,
    )

    await svc.regenerate_state(
        thread_id=1,
        assistant_message_id=42,
        bot=bot,
        request=request,
    )

    assert len(llm.calls) == 1, "expected state LLM to run for RP bot"
    assert len(msgs.update_state_calls) == 1
    msg_id, state = msgs.update_state_calls[0]
    assert msg_id == 42
    assert state.startswith("```yaml")
