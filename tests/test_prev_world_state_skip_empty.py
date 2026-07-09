"""Tests for prev_world_state selection in
``ChatService._build_request``.

The previous-turn state passed to the orchestrator must come
from the most recent assistant message that actually HAS a
non-empty state — not from the most recent assistant message
period. Two reasons:

1. Race during fast regenerate: the state-update regenerator
   runs asynchronously after ``stream_message`` saves the
   assistant row, so a quick edit / regenerate / new user
   message can fire while the previous one still has state=NULL
   (or empty). Picking that empty row would feed an empty
   ``[World state from previous turn]`` block into the prompt
   (or skip it entirely, which makes the model hallucinate a
   fresh world).

2. Crash / dropped update: if the background task crashed,
   ``Conversation.state`` stays None forever for that row.
   The next turn must reach further back to a surviving state
   rather than starting from nothing.

The state-update regenerator already follows this contract
via ``get_previous_assistant_state`` (SQL with
``state IS NOT NULL AND state != ''``). These tests pin the
matching contract on the chat-prompt assembly path so the two
can't drift.

History ordering: ``list_for_thread`` returns oldest-first
(it reverses the SQL DESC inside its row-mapper to make the
DTO happy); the caller iterates with ``reversed(history)``
to get newest-first when picking the most-recent assistant.
The fixtures below match the same convention.
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
    MessageDTO,
    SendMessageCommand,
)
from app.application.services.chat import ChatService  # noqa: E402


def _make_bot():
    return SimpleNamespace(
        id=1,
        name="Test",
        personality="",
        scenario="",
        first_message="",
        mes_example="",
        world_state_prompt="emit yaml",
        dynamic_system_prompt="stay in character",
        bot_type="rp",
    )


class _NoOpBotsRepo:
    def __init__(self, bot):
        self._bot = bot

    async def get(self, bot_id):
        return self._bot


class _NoOpMessagesRepo:
    def __init__(self):
        self.update_state_calls: list = []

    async def save(self, *args, **kwargs):
        return 1

    async def list_for_thread(self, *args, **kwargs):
        return []

    async def update_state(self, message_id, state):
        self.update_state_calls.append((message_id, state))

    async def get_previous_assistant_state(self, *args, **kwargs):
        return ""


def _msg(id_, role, content="x", state=None):
    """Build a MessageDTO with state as the project schema defines.

    state is **str | None** in MessageDTO; passing None means the
    state-update hasn't landed yet (race) or the message predates
    the feature.
    """
    return MessageDTO(id=id_, role=role, content=content, state=state)


async def _build_for_history(bot, history):
    """Run ``_build_request`` with the given bot + history and
    return the populated ``ConversationRequest``.

    Stubs every collaborator that ``_build_request`` touches
    besides ``list_for_thread`` (which is what we override
    here) so the test doesn't drag in Chroma / OpenAI / SQL.
    """
    bots = _NoOpBotsRepo(bot)
    msgs = _NoOpMessagesRepo()
    svc = ChatService(bots=bots, messages=msgs, knowledge=None, orchestrator=None)
    command = SendMessageCommand(
        thread_id=1, bot_id=1, user_input="hi", file_ids=[], persona_id=None
    )
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
    svc._knowledge = AsyncMock(search=AsyncMock(return_value=[]))
    svc._files = None
    return await svc._build_request(command)


@pytest.mark.asyncio
async def test_prev_state_skips_empty_assistant_and_keeps_going() -> None:
    """Most recent assistant has state=None (state-update didn't
    land). The next older assistant has a real state. The
    previous-state block must come from that older one, not the
    new one.
    """
    bot = _make_bot()
    history = [
        _msg(50, "assistant", state="```yaml\nolder: 1\n```"),
        _msg(99, "user"),
        _msg(100, "assistant", state="```yaml\nactual: 1\n```"),
        _msg(199, "user"),
        _msg(200, "assistant", state=None),  # empty → must be skipped
    ]
    request = await _build_for_history(bot, history)
    assert request.prev_world_state == "```yaml\nactual: 1\n```", (
        f"prev_world_state must skip the empty-state assistant (id=200) "
        f"and pick the most recent non-empty one (id=100). "
        f"Got {request.prev_world_state!r}"
    )


@pytest.mark.asyncio
async def test_prev_state_empty_when_all_assistants_empty() -> None:
    """No assistant in the history has a state — the prompt
    must receive empty (which the orchestrator then silently
    drops via the ``if request.prev_world_state.strip()``
    guard). Same as the fresh-thread case.
    """
    bot = _make_bot()
    history = [
        _msg(50, "assistant", state="   "),  # whitespace-only also empty
        _msg(99, "user"),
        _msg(100, "assistant", state=None),
        _msg(199, "user"),
        _msg(200, "assistant", state=""),
    ]
    request = await _build_for_history(bot, history)
    assert request.prev_world_state == "", (
        f"When no assistant has a real state, prev_world_state must "
        f"be empty (orchestrator drops the block). Got {request.prev_world_state!r}"
    )


@pytest.mark.asyncio
async def test_prev_state_picks_first_non_empty_in_reverse() -> None:
    """Sanity check — when the most recent assistant already
    has a state (the happy path), we still pick it. This is
    unchanged behaviour but worth pinning so the new skip logic
    doesn't regress the simple case.
    """
    bot = _make_bot()
    happy_state = "```yaml\nuser:\n  health: 80\n```"
    history = [
        _msg(100, "assistant", state="```yaml\nolder: 1\n```"),
        _msg(199, "user"),
        _msg(200, "assistant", state=happy_state),
    ]
    request = await _build_for_history(bot, history)
    assert request.prev_world_state == happy_state, (
        f"Sanity check failed: most-recent assistant's state must be "
        f"picked in the happy path. Got {request.prev_world_state!r}"
    )


@pytest.mark.asyncio
async def test_prev_state_skips_whitespace_only_and_empty() -> None:
    """Edge case: leading assistant rows have state='',
    state=None, state=' ' (whitespace). None counts as a real
    state; only an actual non-empty trimmed string does.
    """
    bot = _make_bot()
    history = [
        _msg(50, "assistant", state="```yaml\nreal: 1\n```"),
        _msg(99, "user"),
        _msg(100, "assistant", state="   "),
        _msg(199, "user"),
        _msg(200, "assistant", state=""),
    ]
    request = await _build_for_history(bot, history)
    assert request.prev_world_state == "```yaml\nreal: 1\n```"


@pytest.mark.asyncio
async def test_prev_state_empty_on_brand_new_thread() -> None:
    """Brand-new thread — first message from the user is in
    history but no assistant turn exists yet. Must return "".
    """
    bot = _make_bot()
    history = [_msg(1, "user")]
    request = await _build_for_history(bot, history)
    assert request.prev_world_state == ""
