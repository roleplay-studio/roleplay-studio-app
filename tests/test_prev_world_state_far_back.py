"""Test: skip-world-state-threshold scenario.

Real-world case the original 0.0.4 prompt-assembly path missed:

  A user is running a long roleplay session. The bot has
  ``world_state_prompt`` so the background regenerator tries
  to write ``Conversation.state`` after every assistant turn.
  Around message 120, the state-update task starts crashing
  (network blip, provider rate limit, whatever) — every
  assistant from id 120 to id 200 has ``state=NULL``. The
  most recent assistant that DOES carry a state is from id
  110, ten turns back.

  Question for this module: when ``_build_request`` walks
  the active history reversed, does it reach that id-110
  row, or does it short-circuit on the first assistant (no
  matter if its state is empty)?

  Pre-fix behaviour: yes, it short-circuited — even on a
  None state — so the next turn went to the LLM with no
  ``[World state from previous turn]`` block.

  Fix (``cdecd0a``): keep walking the history until we find
  an assistant with a non-empty state. If no assistant in the
  thread has a state, fall back to empty / "fresh start".

  This test pinpoints the 10-messages-back case as the
  canonical example to keep the loop honest.
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

from app.application.dto import MessageDTO, SendMessageCommand  # noqa: E402
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
    async def save(self, *args, **kwargs):
        return 1

    async def list_for_thread(self, *args, **kwargs):
        return []

    async def update_state(self, *args, **kwargs):
        pass

    async def get_previous_assistant_state(self, *args, **kwargs):
        return ""


async def _build_for_history(bot, history):
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


def _msg(id_, role, content="x", state=None):
    return MessageDTO(id=id_, role=role, content=content, state=state)


@pytest.mark.asyncio
async def test_prev_state_picked_from_10_turns_back_when_recent_ones_empty() -> None:
    """The headline scenario: state-update broke 10 turns ago.
    The 10 most recent assistant rows are all state=None.
    The 11th (id=10) has the last surviving state. The prompt
    must carry that 10-turns-old state forward, not start from
    nothing.
    """
    bot = _make_bot()
    # Build a history alternating user/assistant. Recent
    # assistants (200 .. 110 in DESC order) all have empty
    # state. The id=50 row still has the last good YAML.
    # ASC-order history (oldest first), as list_for_thread
    # produces.
    history: list[MessageDTO] = []
    for i in range(10, 211, 10):
        # user message at (i-1), assistant at i
        history.append(_msg(i - 1 if i - 1 > 0 else 1, "user"))
        history.append(
            _msg(i, "assistant", state=None)  # empty
            if i > 100
            else _msg(i, "assistant", state="```yaml\nlast_good: 1\n```")
        )

    # Verify setup: at least 10 assistant rows after id=100, all
    # state=None, and id=50 has the last non-empty state.
    recent_assistants = [m for m in history if m.role == "assistant" and m.id > 100]
    older_assistants = [m for m in history if m.role == "assistant" and m.id <= 100]
    assert len(recent_assistants) >= 10
    assert all(m.state is None for m in recent_assistants)
    assert any(m.state and "last_good" in m.state for m in older_assistants)

    request = await _build_for_history(bot, history)
    assert request.prev_world_state == "```yaml\nlast_good: 1\n```", (
        f"prev_world_state must reach past 10 empty-state assistants to the "
        f"most recent survivor. Got {request.prev_world_state!r}"
    )


@pytest.mark.asyncio
async def test_prev_state_truly_empty_when_no_assistant_ever_had_state() -> None:
    """Edge case complement: if NO assistant in the entire
    thread has a state (e.g. a brand new bot whose
    ``world_state_prompt`` was just enabled), the prompt gets
    no world-state block. The LLM will start the world from
    its conversation context — that's correct, no prior
    commitment exists. We don't want to fall back to a hard-
    coded "fresh world" template because that's the LLM's
    job, not ours.
    """
    bot = _make_bot()
    history = [
        _msg(10, "user"),
        _msg(11, "assistant", state=None),
        _msg(20, "user"),
        _msg(21, "assistant", state=None),
        _msg(30, "user"),
        _msg(31, "assistant", state=""),
    ]
    request = await _build_for_history(bot, history)
    assert request.prev_world_state == "", (
        f"When no assistant ever had a state, prev_world_state must be empty. "
        f"Got {request.prev_world_state!r}"
    )
