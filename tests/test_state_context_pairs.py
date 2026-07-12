"""Tests for the configurable state-context window in
``ChatService.regenerate_state``.

Background
----------
Before this change, ``regenerate_state`` fed the LLM only the
*current* user message and the *current* assistant response, plus
the previous assistant's ``state``. Everything between
``state[N-1]`` and ``state[N]`` was lost — the LLM had to guess
what happened by extrapolating from the state alone. For sessions
with rich world state (NPCs, multiple factions, ongoing quests)
that meant every few turns the regenerator would drop details
the user cared about.

The fix lets the operator tune how many user/assistant pairs the
LLM sees via ``Settings.state_context_pairs`` (env
``STATE_CONTEXT_PAIRS``). The default is 10 pairs (matching the
``SUMMARIZE_RECENT_LIMIT`` ceiling the rest of the codebase uses
for "recent" windows) and ``0`` keeps the legacy behaviour for
operators that want a strict minimal prompt.

Why tests matter here
---------------------
This is a 3-layer change:
  - new Settings field
  - new ``_build_recent_conversation`` helper that walks
    ``list_for_thread`` with ``before_id=assistant_message_id``
  - LLM-prompt assembly in ``regenerate_state``

All three must stay in sync. A test that asserts the prompt body
contains the right user/assistant pair count catches drift at
every layer.
"""

from __future__ import annotations

import sys
from types import SimpleNamespace
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
from app.infrastructure.config import Settings  # noqa: E402

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
    """In-memory fake that mirrors the SQL contract the real repo
    uses (DESC order, ``before_id`` filter applied before sorting).
    See ``AGENTS.md`` → "⚠️ Критично: фейковые репозитории должны
    моделировать реальный SQL-контракт" — this class is the
    minimal faithful reproduction needed for state-context tests.
    """

    def __init__(self) -> None:
        self.saved_states: dict[int, str] = {}
        # Stored as SimpleNamespace so the orchestrator's
        # _load_assistant_content can read ``m.id`` / ``m.content``
        # without mocking the full MessageDTO surface.
        self._rows: list[SimpleNamespace] = []

    async def list_for_thread(self, thread_id, limit=200, before_id=None):
        # SQL contract: ``before_id`` is applied FIRST, then order
        # DESC, then limit. Returns newest-first.
        filtered = [r for r in self._rows if before_id is None or r.id < before_id]
        filtered.sort(key=lambda r: r.id, reverse=True)
        return filtered[:limit]

    async def get_previous_assistant_state(self, thread_id, before_message_id=None):
        candidates = [
            (r.id, r.state or "")
            for r in self._rows
            if r.role == "assistant"
            and (before_message_id is None or r.id < before_message_id)
        ]
        if not candidates:
            return ""
        return max(candidates, key=lambda kv: kv[0])[1]

    async def update_state(self, message_id: int, state: str) -> None:
        self.saved_states[message_id] = state

    def add(self, msg_id: int, role: str, content: str, state: str = "") -> None:
        self._rows.append(
            SimpleNamespace(id=msg_id, role=role, content=content, state=state)
        )


def _make_bot():
    bot = MagicMock()
    bot.id = 1
    bot.world_state_prompt = WORLD_STATE_PROMPT
    bot.dynamic_system_prompt = ""
    bot.bot_type = "rp"
    return bot


def _make_request(user_input: str = "current user line") -> ConversationRequest:
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


class _CapturingLLM:
    """Records every call to ``generate_response`` so tests can
    assert on the messages the LLM actually saw.
    """

    def __init__(self, response: str = "```yaml\nstate: ok\n```") -> None:
        self.calls: list[dict] = []
        self._response = response

    async def generate_response(self, messages, **kwargs):
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return self._response


def _user_prompt(call: dict) -> str:
    """Extract the single 'user' message content from a captured call.

    The state-gen prompt is system + user (no history array), so
    there's exactly one user message.
    """
    for m in call["messages"]:
        if m["role"] == "user":
            return m["content"]
    raise AssertionError(f"No user-role message in: {call['messages']!r}")


# ─── Defaults ────────────────────────────────────────────────────────


def test_settings_state_context_pairs_default_is_ten() -> None:
    """Default must be 10 pairs — matches SUMMARIZE_RECENT_LIMIT
    ceiling used elsewhere for 'recent' windows. Tunable via
    STATE_CONTEXT_PAIRS env var.
    """
    settings = Settings()
    assert settings.state_context_pairs == 10
    assert isinstance(settings.state_context_pairs, int)
    assert settings.state_context_pairs >= 0


def test_settings_state_context_pairs_env_override() -> None:
    """The env var must override the default (pydantic-settings
    convention). ``0`` is a valid value — it means 'use the legacy
    minimal prompt'.
    """
    import os

    prev = os.environ.pop("STATE_CONTEXT_PAIRS", None)
    try:
        os.environ["STATE_CONTEXT_PAIRS"] = "3"
        assert Settings().state_context_pairs == 3

        os.environ["STATE_CONTEXT_PAIRS"] = "0"
        assert Settings().state_context_pairs == 0
    finally:
        if prev is not None:
            os.environ["STATE_CONTEXT_PAIRS"] = prev
        else:
            os.environ.pop("STATE_CONTEXT_PAIRS", None)


def test_settings_state_context_pairs_rejects_negative() -> None:
    """Negative values would mean 'silently drop pairs from the
    middle' — easy to misconfigure, no useful semantics. Pydantic
    Field(ge=0) catches this at construction.
    """
    import os

    prev = os.environ.pop("STATE_CONTEXT_PAIRS", None)
    try:
        os.environ["STATE_CONTEXT_PAIRS"] = "-1"
        with pytest.raises(Exception):  # ValidationError or ValueError
            Settings()
    finally:
        if prev is not None:
            os.environ["STATE_CONTEXT_PAIRS"] = prev
        else:
            os.environ.pop("STATE_CONTEXT_PAIRS", None)


# ─── regenerate_state behaviour ─────────────────────────────────────


def _service_with_settings(pairs: int) -> tuple[ChatService, _CapturingLLM, _FakeMessagesRepo, Settings]:
    """Build a ChatService wired to a Settings with a custom
    state_context_pairs. Other settings default.
    """
    settings = Settings(state_context_pairs=pairs)
    bot = _make_bot()
    bots = _FakeBotsRepo(bot)
    msgs = _FakeMessagesRepo()
    llm = _CapturingLLM()
    svc = ChatService(
        bots=bots, messages=msgs, knowledge=None, orchestrator=None, llm=llm, settings=settings
    )
    return svc, llm, msgs, settings


async def _seed_conversation(msgs: _FakeMessagesRepo) -> None:
    """Seed a conversation long enough to exercise the
    'last N pairs' window selection. We need MORE than 2*N
    rows to verify the window trims correctly. With
    ``state_context_pairs=3`` the window is 6 rows; we
    seed 8 prior rows (4 complete pairs) so the oldest pair
    falls outside the window.

    IDs increase; current assistant message id is 90.
    """
    msgs.add(10, "user", "user line 1")
    msgs.add(20, "assistant", "assistant line 1", state="state-1")
    msgs.add(30, "user", "user line 2")
    msgs.add(40, "assistant", "assistant line 2", state="state-2")
    msgs.add(50, "user", "user line 3")
    msgs.add(60, "assistant", "assistant line 3", state="state-3")
    msgs.add(70, "user", "user line 4")
    msgs.add(80, "assistant", "assistant line 4", state="state-4")
    msgs.add(90, "assistant", "assistant line 5", state="")


@pytest.mark.asyncio
async def test_state_context_pairs_3_includes_three_previous_pairs() -> None:
    """With ``state_context_pairs=3``, the LLM prompt must contain
    the 3 user/assistant pairs immediately preceding the current
    assistant message — and NOT the current pair (which is sent
    in the separate ``User message:`` / ``Assistant response:``
    blocks).

    Seeded conversation (newest last):
        id=90 assistant "assistant line 5"  ← current (regenerate target)
        id=80 assistant "assistant line 4"  ← pair 4 (newest prior)
        id=70 user      "user line 4"
        id=60 assistant "assistant line 3"  ← pair 3
        id=50 user      "user line 3"
        id=40 assistant "assistant line 2"  ← pair 2
        id=30 user      "user line 2"
        id=20 assistant "assistant line 1"  ← pair 1 — OUTSIDE window
        id=10 user      "user line 1"

    With pairs=3 the window is 6 rows (limit=2*3); only the last
    6 prior rows fit, so "user line 1" + "assistant line 1" must
    fall off the end.
    """
    svc, llm, msgs, _settings = _service_with_settings(pairs=3)
    await _seed_conversation(msgs)
    bot = MagicMock()
    bot.world_state_prompt = WORLD_STATE_PROMPT
    bot.bot_type = "rp"

    await svc.regenerate_state(
        thread_id=1, assistant_message_id=90, bot=bot, request=_make_request("current user line")
    )

    assert len(llm.calls) == 1, "regenerate_state must call the LLM exactly once"
    user_content = _user_prompt(llm.calls[0])

    # The 3 previous pairs must be present.
    assert "user line 3" in user_content
    assert "assistant line 3" in user_content
    assert "user line 4" in user_content
    assert "assistant line 4" in user_content
    # The current assistant response (which is sent in its own
    # labelled block) must be present too.
    assert "assistant line 5" in user_content
    assert "current user line" in user_content

    # The oldest pair must NOT appear — it fell off the window.
    assert "user line 1" not in user_content, (
        f"Pair 1 should be outside the 3-pair window; got: {user_content!r}"
    )
    assert "assistant line 1" not in user_content


@pytest.mark.asyncio
async def test_state_context_pairs_0_keeps_legacy_minimal_prompt() -> None:
    """With ``state_context_pairs=0``, the prompt must contain
    ONLY the previous state, current user input, and current
    assistant response — exactly the pre-feature format. This
    is the backward-compat knob.
    """
    svc, llm, msgs, _settings = _service_with_settings(pairs=0)
    await _seed_conversation(msgs)
    bot = MagicMock()
    bot.world_state_prompt = WORLD_STATE_PROMPT
    bot.bot_type = "rp"

    await svc.regenerate_state(
        thread_id=1, assistant_message_id=90, bot=bot, request=_make_request("current user line")
    )

    user_content = _user_prompt(llm.calls[0])
    assert "user line 2" not in user_content
    assert "assistant line 2" not in user_content
    assert "user line 3" not in user_content
    # Previous state, current user input, and current assistant
    # response MUST still be there.
    assert "state-4" in user_content
    assert "current user line" in user_content
    assert "assistant line 5" in user_content


@pytest.mark.asyncio
async def test_state_context_pairs_exceeding_history_uses_what_is_there() -> None:
    """If the conversation has fewer pairs than requested
    (e.g. a fresh thread with just the current exchange), the
    LLM must still get whatever is available — no error, no
    padding, no dropped current exchange.
    """
    svc, llm, msgs, _settings = _service_with_settings(pairs=10)
    # Only the current exchange, nothing before it.
    msgs.add(60, "assistant", "assistant line 3")
    bot = MagicMock()
    bot.world_state_prompt = WORLD_STATE_PROMPT
    bot.bot_type = "rp"

    await svc.regenerate_state(
        thread_id=1, assistant_message_id=60, bot=bot, request=_make_request("current user line")
    )

    user_content = _user_prompt(llm.calls[0])
    # Current user + current assistant still present.
    assert "current user line" in user_content
    assert "assistant line 3" in user_content


@pytest.mark.asyncio
async def test_recent_conversation_block_is_present_and_well_formed() -> None:
    """When pairs > 0, the prompt must carry a labelled
    ``Recent conversation:`` block — the LLM uses this header
    to distinguish the running dialogue from the previous-state
    snapshot. A free-floating list without the label is harder
    for smaller models to parse correctly.
    """
    svc, llm, msgs, _settings = _service_with_settings(pairs=2)
    msgs.add(50, "user", "earlier user line")
    msgs.add(60, "assistant", "earlier assistant line")
    msgs.add(70, "user", "current user input")
    msgs.add(80, "assistant", "current assistant output")
    bot = MagicMock()
    bot.world_state_prompt = WORLD_STATE_PROMPT
    bot.bot_type = "rp"

    await svc.regenerate_state(
        thread_id=1, assistant_message_id=80, bot=bot, request=_make_request("current user input")
    )

    user_content = _user_prompt(llm.calls[0])
    # Labelled section header present.
    assert "Recent conversation" in user_content, (
        f"Missing 'Recent conversation' label; prompt was: {user_content!r}"
    )
    # The earlier user/assistant line is in the window.
    assert "earlier user line" in user_content
    assert "earlier assistant line" in user_content
