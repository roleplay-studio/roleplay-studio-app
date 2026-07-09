"""Tests for the floating system prompt + world-state features.

Covers Phase 1 / Phase 2 of the plan:
- orchestrator injects the floating system prompt in the right
  position (before the last user message, with ``[Reminder]``
  framing),
- variable substitution applies ({{char}}, {{user}}),
- empty / unset floating prompt is a no-op,
- state regeneration persists the LLM response verbatim (no
  parsing, no truncation beyond the 4 KB ceiling),
- the manual regenerate_state endpoint accepts the right body.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.application.dto import ConversationRequest, MessageDTO
from app.infrastructure.db.models import Bot
from app.infrastructure.orchestration.langgraph_orchestrator import (
    LangGraphConversationOrchestrator,
)

# ── Orchestrator: floating prompt injection ─────────────────────────


class _StubLLM:
    """Returns a fixed chunk so we can assert on the final messages array."""

    async def generate_response(self, messages, **_kwargs):
        # Echo the messages back as the response — enough to assert
        # what was sent without a real LLM.
        yield type("Chunk", (), {"content": "ok", "reasoning": None, "usage": None,
                                  "debug_messages": messages})()


class _StubPreamble:
    def fallback(self) -> str:
        return ""

    def get(self, _bot_type):
        return ""


def _build_orchestrator() -> LangGraphConversationOrchestrator:
    from app.infrastructure.config import Settings

    settings = Settings(_env_file=None)
    return LangGraphConversationOrchestrator(
        llm=_StubLLM(),  # type: ignore[arg-type]
        settings=settings,
        preamble_provider=_StubPreamble(),  # type: ignore[arg-type]
    )


def _make_request(
    history: list[MessageDTO],
    *,
    dynamic_system_prompt: str = "",
    prev_world_state: str = "",
) -> ConversationRequest:
    return ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        bot_name="Lili",
        bot_personality="friendly",
        bot_scenario="",
        first_message="",
        bot_type="rp",
        history=history,
        untrusted_context=[],
        dynamic_system_prompt=dynamic_system_prompt,
        prev_world_state=prev_world_state,
    )


def _run_user_input_node(
    prompt: str = "",
    history: list[MessageDTO] | None = None,
    prev_world_state: str = "",
):
    """Build the orchestrator state up to user_input and return final messages."""

    orch = _build_orchestrator()
    request = _make_request(
        history or [],
        dynamic_system_prompt=prompt,
        prev_world_state=prev_world_state,
    )
    state: dict[str, Any] = {
        "messages": [
            {"role": "system", "content": "<Persona>...</Persona>"},
            {"role": "user", "content": "old turn"},
        ],
        "request": request,
        "response": None,
        "bot_type": "rp",
    }
    new_state = orch._node_user_input(state)
    return new_state["messages"]


def test_empty_floating_prompt_is_noop():
    messages = _run_user_input_node(prompt="")
    # Last message is the raw user input; no Reminder block was added.
    assert messages[-1] == {"role": "user", "content": "hi"}
    assert not any(m["role"] == "system" and "[Reminder]" in m["content"] for m in messages)


def test_floating_prompt_inserted_before_user_input():
    messages = _run_user_input_node(prompt="Stay in character")
    assert len(messages) >= 3
    assert messages[-2] == {
        "role": "system",
        "content": "[Reminder] Stay in character",
    }
    assert messages[-1] == {"role": "user", "content": "hi"}


def test_floating_prompt_variable_substitution():
    """``{{char}}`` substitutes to the bot name (the only variable
    available when no ``user_persona`` is attached to the request)."""
    messages = _run_user_input_node(prompt="Greet {{user}} in {{char}}'s style")
    # Without a user_persona, {{user}} stays as the literal token
    # (see _variable_replace in langgraph_orchestrator.py).
    assert messages[-2]["content"] == "[Reminder] Greet {{user}} in Lili's style"


def test_world_state_injected_after_reminder_before_user():
    """When both reminder and prev_world_state are present, the
    final three messages are reminder → state → user, in that order.

    Verifies the bundle layout that lets the LLM see "reminder →
    world context → user turn" as a single coherent prefix before
    generating the next assistant response.
    """
    messages = _run_user_input_node(
        prompt="Stay in character",
        prev_world_state="location: tavern\ntime: noon",
    )
    assert messages[-3]["content"] == "[Reminder] Stay in character"
    assert messages[-2]["content"] == (
        "[World state from previous turn] location: tavern\ntime: noon"
    )
    assert messages[-1] == {"role": "user", "content": "hi"}


def test_world_state_without_reminder_still_injected():
    """When prev_world_state is set but reminder is empty, state
    still appears right before the user turn. Order: user → state →
    user-msg. Keeps the contract symmetric so operators don't have
    to remember which combination hides which block."""
    messages = _run_user_input_node(
        prompt="",
        prev_world_state="location: library",
    )
    # Only the state block was appended (no Reminder).
    assert not any(
        m["role"] == "system" and "[Reminder]" in m["content"] for m in messages
    )
    assert messages[-2]["content"] == "[World state from previous turn] location: library"
    assert messages[-1] == {"role": "user", "content": "hi"}


def test_empty_prev_world_state_is_noop():
    """Empty prev_world_state (very first user message of a new
    thread, or the previous assistant turn hadn't produced a state
    yet) doesn't insert a placeholder system message."""
    messages = _run_user_input_node(prompt="", prev_world_state="")
    assert not any(
        "[World state from previous turn]" in m["content"]
        for m in messages
        if m["role"] == "system"
    )


def test_whitespace_only_floating_prompt_is_noop():
    messages = _run_user_input_node(prompt="   \n  \t  ")
    assert messages[-1] == {"role": "user", "content": "hi"}
    assert not any("[Reminder]" in m["content"] for m in messages if m["role"] == "system")


# ── MessageDTO stamping ────────────────────────────────────────────


def test_message_dto_carries_state_and_dynamic_system_prompt():
    """The DTO accepts the two new optional fields without breaking
    the literal type on `role`."""
    msg = MessageDTO(
        id=1,
        role="assistant",
        content="ok",
        state="location: tavern",
        dynamic_system_prompt="stay in character",
    )
    assert msg.state == "location: tavern"
    assert msg.dynamic_system_prompt == "stay in character"


def test_message_dto_state_and_dynamic_default_none():
    msg = MessageDTO(id=1, role="user", content="hi")
    assert msg.state is None
    assert msg.dynamic_system_prompt is None


# ── State regeneration: verbatim persistence + truncation ──────────


class _FakeMessagesRepo:
    """Captures update_state calls so we can assert verbatim persistence.

    Mirrors the real ``SqlAlchemyMessageRepository.list_for_thread`` contract:
    DESC order (newest → oldest) on the wire, filtered by ``before_id``
    when given. ``regenerate_state`` walks this from the end (oldest →
    newest) to find the previous assistant's state — so callers must
    iterate ``reversed(history)`` defensively. Tests that violate that
    contract here will (correctly) fail and force the fix.
    """

    def __init__(self):
        self.states: dict[int, str] = {}
        self._rows: list[MessageDTO] = [
            # Pre-seeded assistant message with id=99 — most existing
            # tests pass ``assistant_message_id=99`` to ``regenerate_state``,
            # and the service bails out cleanly if the message is
            # absent (correct behaviour, but breaks the round-trip
            # tests below). Adding it here keeps the historical
            # contract: "this fakerepo is happy with regenerate_state
            # for id=99".
            MessageDTO(
                id=99, role="assistant", content="seeded assistant",
                state=None, is_active=True,
            ),
            MessageDTO(
                id=2, role="user", content="prev user",
                state=None, is_active=True,
            ),
            MessageDTO(
                id=1, role="assistant", content="prev assistant",
                state="prev_state_value", is_active=True,
            ),
        ]
        self.list_calls = 0

    async def list_for_thread(self, thread_id, limit=20, before_id=None):
        self.list_calls += 1
        rows = list(self._rows)
        if before_id is not None:
            rows = [r for r in rows if r.id is not None and r.id < before_id]
        rows.sort(key=lambda r: (r.id or 0), reverse=True)
        return rows[:limit]

    async def update_state(self, message_id: int, state: str) -> None:
        self.states[message_id] = state
        # Keep the in-memory row in sync so callers that re-read via
        # list_for_thread (and the test that asserts round-trip state)
        # see the freshly-written value.
        for r in self._rows:
            if r.id == message_id:
                r.state = state
                return
        # If the row isn't in the seed (the assistant message we just
        # saved), synthesise it so a subsequent list_for_thread sees it.
        self._rows.append(
            MessageDTO(
                id=message_id, role="assistant", content="seed",
                state=state, is_active=True,
            )
        )

    async def get_previous_assistant_state(
        self, thread_id, before_message_id=None
    ) -> str:
        """Mirror the real ``SqlAlchemyMessageRepository.get_previous_assistant_state``.

        Walks the rows in DESC id order, picks the first assistant with
        a non-empty state, optionally restricted to id <
        ``before_message_id``. Returns ``""`` if nothing matches.
        """
        candidates = [
            r for r in self._rows
            if r.role == "assistant"
            and r.state
            and (before_message_id is None or (r.id is not None and r.id < before_message_id))
        ]
        candidates.sort(key=lambda r: r.id or 0, reverse=True)
        if not candidates:
            return ""
        return candidates[0].state or ""

    async def get_first_assistant(self, thread_id):
        for r in self._rows:
            if r.role == "assistant":
                return r
        return None

    async def save_first_assistant_if_absent(self, thread_id, content):
        for r in self._rows:
            if r.role == "assistant":
                return False
        self._rows.append(
            MessageDTO(id=99, role="assistant", content=content, is_active=True)
        )
        return True


class _StubFastLLM:
    """LLM that returns whatever string we hand it."""

    def __init__(self, response: str):
        self.response = response
        self.last_messages = None

    async def generate_response(self, messages, **_kwargs):
        self.last_messages = messages
        return self.response


@pytest.mark.asyncio
async def test_state_persisted_verbatim_no_parsing():
    """Whatever the LLM returns goes into Conversation.state verbatim
    — YAML, JSON, prose, anything."""
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    fake_msgs = _FakeMessagesRepo()
    llm = _StubFastLLM(response="some prose summary, not even yaml")
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )

    bot = Bot(
        id=1,
        name="Lili",
        personality="friendly",
        scenario="",
        first_message="",
        bot_type="rp",
        dynamic_system_prompt="",
        world_state_prompt="emit a YAML block",
    )
    request = ConversationRequest(
        thread_id=1,
        bot_id=1,
        user_input="hi",
        bot_name="Lili",
        bot_personality="friendly",
        bot_scenario="",
        first_message="",
        bot_type="rp",
        history=[],
        untrusted_context=[],
    )

    await service.regenerate_state(thread_id=1, assistant_message_id=99, bot=bot, request=request)

    assert fake_msgs.states == {99: "some prose summary, not even yaml"}


@pytest.mark.asyncio
async def test_state_truncated_at_4mb():
    """Runaway LLM output gets clipped to 4 MiB with a log warning.

    The cap exists to keep a runaway prompt from bloating every
    message row and the JSON we send on every listMessages refresh.
    A 4 MiB ceiling is generous — normal YAML/JSON/prose snapshots
    are kilobytes, not megabytes — so this only kicks in on genuine
    model malfunctions.
    """
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    # 4 MiB + 1 byte — should be clipped to 4 MiB exactly.
    max_cap = 4 * 1024 * 1024
    big = "x" * (max_cap + 1)
    fake_msgs = _FakeMessagesRepo()
    # The service reads the assistant's persisted content via
    # _load_assistant_content before the LLM call; we need the row
    # to exist or the test silently bails (correct prod behaviour,
    # but breaks the truncation assertion).
    fake_msgs._rows.append(
        MessageDTO(
            id=42, role="assistant", content="just-streamed assistant turn",
            state=None, is_active=True,
        )
    )
    llm = _StubFastLLM(response=big)
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )

    bot = Bot(
        id=1,
        name="Lili",
        personality="friendly",
        scenario="",
        first_message="",
        bot_type="rp",
        dynamic_system_prompt="",
        world_state_prompt="emit",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="Lili", bot_personality="friendly", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )

    await service.regenerate_state(thread_id=1, assistant_message_id=42, bot=bot, request=request)

    assert fake_msgs.states[42] == "x" * max_cap
    assert len(fake_msgs.states[42]) == max_cap


@pytest.mark.asyncio
async def test_state_skipped_on_llm_error():
    """If the LLM call fails, no state write happens and no exception
    propagates (fire-and-forget contract)."""
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    class _BoomLLM:
        async def generate_response(self, _messages, **_kwargs):
            raise RuntimeError("provider down")

    fake_msgs = _FakeMessagesRepo()
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=_BoomLLM(),  # type: ignore[arg-type]
    )

    bot = Bot(
        id=1, name="Lili", personality="friendly", scenario="",
        first_message="", bot_type="rp",
        dynamic_system_prompt="", world_state_prompt="emit",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="Lili", bot_personality="friendly", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )

    # Must not raise.
    await service.regenerate_state(thread_id=1, assistant_message_id=42, bot=bot, request=request)
    assert fake_msgs.states == {}


# ── Round-trip: state-gen request carries the previous state ───────


@pytest.mark.asyncio
async def test_state_gen_passes_previous_state_to_llm():
    """The LLM-call payload includes the previous assistant's state so
    the model can mutate it rather than start from scratch."""
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    fake_msgs = _FakeMessagesRepo()
    llm = _StubFastLLM(response="next_state")
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )

    bot = Bot(
        id=1, name="Lili", personality="friendly", scenario="",
        first_message="", bot_type="rp",
        dynamic_system_prompt="", world_state_prompt="emit yaml",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="Lili", bot_personality="friendly", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )

    await service.regenerate_state(thread_id=1, assistant_message_id=99, bot=bot, request=request)

    assert llm.last_messages is not None
    assert llm.last_messages[0]["role"] == "system"
    assert llm.last_messages[0]["content"] == "emit yaml"
    # The user message includes the previous state value from the
    # fake repo's ``history`` fixture.
    assert "prev_state_value" in llm.last_messages[1]["content"]


# ── Realistic multi-message histories: bug-reproducing cases ──────────
#
# These mirror the actual SQL contract: ``list_for_thread`` returns
# messages in **DESC** order (newest → oldest), filtered by ``before_id``.
# The naive ``history[-1].state`` lookup in ``regenerate_state`` works
# for the simple two-row fixture but breaks as soon as the thread has
# 3+ rows in the DESC window — ``limit=2`` slices off the assistant row
# and ``[-1]`` lands on a user message.


def _seed_three_message_history(repo: _FakeMessagesRepo) -> None:
    """Pre-populate a thread that looks like the realistic chat flow:
    [assistant(first_message), user, assistant, user] — DESC reads as
    [user(id=4), assistant(id=3, has state), user(id=2), assistant(id=1)].

    The fix has to find the most recent assistant with non-empty state
    even when ``list_for_thread(limit=2, before_id=N)`` returns two
    user messages because the assistant fell out of the window.
    """
    repo._rows = [
        MessageDTO(
            id=4, role="user", content="u3", state=None, is_active=True,
        ),
        MessageDTO(
            id=3, role="assistant", content="a3",
            state="state_at_id_3", is_active=True,
        ),
        MessageDTO(
            id=2, role="user", content="u2", state=None, is_active=True,
        ),
        MessageDTO(
            id=1, role="assistant", content="a1",
            state="state_at_id_1", is_active=True,
        ),
        # The assistant message we just streamed — ``regenerate_state``
        # looks up its content via ``_load_assistant_content`` before
        # calling the LLM. Without this row, the service silently
        # bails (correct behaviour, but breaks the test).
        MessageDTO(
            id=99, role="assistant", content="just-streamed assistant turn",
            state=None, is_active=True,
        ),
    ]


@pytest.mark.asyncio
async def test_state_gen_picks_correct_prev_assistant_with_realistic_history():
    """A 3+ message thread: ``list_for_thread(limit=2, before_id=99)``
    returns [user, user] in DESC — the assistant row is below the window.
    ``regenerate_state`` must walk the full history (not the truncated
    window) to find the most recent assistant's state.
    """
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    fake_msgs = _FakeMessagesRepo()
    _seed_three_message_history(fake_msgs)
    llm = _StubFastLLM(response="next_state")
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )

    bot = Bot(
        id=1, name="Lili", personality="friendly", scenario="",
        first_message="", bot_type="rp",
        dynamic_system_prompt="", world_state_prompt="emit yaml",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="Lili", bot_personality="friendly", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )

    await service.regenerate_state(thread_id=1, assistant_message_id=99, bot=bot, request=request)

    assert llm.last_messages is not None
    # Most recent assistant is id=3 with state "state_at_id_3".
    assert "state_at_id_3" in llm.last_messages[1]["content"], (
        f"expected the most recent assistant state; got: {llm.last_messages[1]['content']!r}"
    )


@pytest.mark.asyncio
async def test_state_gen_skips_assistants_without_state():
    """If the most recent assistant has empty state (state-update
    hadn't landed yet), ``regenerate_state`` should walk back to the
    previous assistant that DOES have state.
    """
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    fake_msgs = _FakeMessagesRepo()
    fake_msgs._rows = [
        MessageDTO(
            id=99, role="assistant", content="just-streamed assistant",
            state=None, is_active=True,
        ),
        MessageDTO(id=4, role="user", content="u3", state=None, is_active=True),
        MessageDTO(id=3, role="assistant", content="a3", state=None, is_active=True),
        MessageDTO(id=2, role="user", content="u2", state=None, is_active=True),
        MessageDTO(id=1, role="assistant", content="a1",
                   state="the_only_state_we_have", is_active=True),
    ]
    llm = _StubFastLLM(response="next_state")
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )

    bot = Bot(
        id=1, name="Lili", personality="", scenario="",
        first_message="", bot_type="rp",
        dynamic_system_prompt="", world_state_prompt="emit",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="L", bot_personality="", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )
    await service.regenerate_state(thread_id=1, assistant_message_id=99, bot=bot, request=request)
    assert "the_only_state_we_have" in llm.last_messages[1]["content"]


@pytest.mark.asyncio
async def test_state_gen_no_previous_assistant_yields_empty_state():
    """Brand-new thread: no prior assistant with state, but the
    assistant message itself exists (no race). The LLM payload's
    user message must say ``(none)`` instead of leaking garbage.
    """
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    fake_msgs = _FakeMessagesRepo()
    # Wipe the default seed and put back only the freshly-streamed
    # assistant message (id=99) — there is no prior assistant with
    # state, but the regenerate target itself is present.
    fake_msgs._rows = [
        MessageDTO(
            id=99, role="assistant", content="just-streamed assistant",
            state=None, is_active=True,
        ),
    ]
    llm = _StubFastLLM(response="next_state")
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )
    bot = Bot(
        id=1, name="L", personality="", scenario="",
        first_message="", bot_type="rp",
        dynamic_system_prompt="", world_state_prompt="emit",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="L", bot_personality="", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )
    await service.regenerate_state(thread_id=1, assistant_message_id=99, bot=bot, request=request)
    assert llm.last_messages is not None, "LLM should have been called"
    assert "(none)" in llm.last_messages[1]["content"]


@pytest.mark.asyncio
async def test_state_gen_uses_fast_llm_not_chat_llm():
    """``regenerate_state`` must call the cheap fast_model, not the
    primary chat model — state is structured-output noise that doesn't
    need the chat-quality model. The chat model would burn tokens on
    YAML/JSON the user never sees.

    Verifies the wiring: the injected ``fast_llm`` is invoked, the
    chat-quality ``llm`` is NOT.
    """
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    fake_msgs = _FakeMessagesRepo()
    fast_llm = _StubFastLLM(response="fast")
    chat_llm = _StubFastLLM(response="chat")

    # Patch ChatService.__init__ defaults — we pass both and verify
    # only fast_llm gets called.
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=chat_llm,  # type: ignore[arg-type]
        fast_llm=fast_llm,  # type: ignore[arg-type]
    )
    bot = Bot(
        id=1, name="L", personality="", scenario="",
        first_message="", bot_type="rp",
        dynamic_system_prompt="", world_state_prompt="emit yaml",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="L", bot_personality="", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )
    await service.regenerate_state(thread_id=1, assistant_message_id=99, bot=bot, request=request)
    assert fast_llm.last_messages is not None, "fast_llm was not called"
    assert chat_llm.last_messages is None, (
        "chat-quality llm should NOT be used for state gen"
    )


@pytest.mark.asyncio
async def test_state_gen_uses_reasonable_max_tokens_not_4mib():
    """Sending 4 MiB max_tokens to a real LLM provider is rejected by
    most (OpenRouter caps at 32k for non-Claude models, OpenAI at 16k).
    The cap for state-gen should be something a YAML snapshot can
    actually use — 2k tokens is generous for any sensible format.
    """
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    fake_msgs = _FakeMessagesRepo()
    captured_kwargs: dict = {}

    class CapturingLLM:
        async def generate_response(self, messages, **kwargs):
            captured_kwargs.update(kwargs)
            return "ok"

    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=CapturingLLM(),  # type: ignore[arg-type]
    )
    bot = Bot(
        id=1, name="L", personality="", scenario="",
        first_message="", bot_type="rp",
        dynamic_system_prompt="", world_state_prompt="emit",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="L", bot_personality="", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )
    await service.regenerate_state(thread_id=1, assistant_message_id=99, bot=bot, request=request)
    assert "max_tokens" in captured_kwargs
    # 4 MiB = 4_194_304. Anything ≤ 8k is sensible.
    assert captured_kwargs["max_tokens"] <= 8192, (
        f"state-gen max_tokens={captured_kwargs['max_tokens']} exceeds LLM provider limits"
    )


@pytest.mark.asyncio
async def test_state_gen_survives_missing_assistant_message():
    """If the assistant message has been deleted between save and
    state-gen (race condition: user clicked delete while background
    state-update was running), the operation must no-op, not crash.
    """
    from app.application.dto import ConversationRequest
    from app.application.services.chat import ChatService

    fake_msgs = _FakeMessagesRepo()
    fake_msgs._rows = []  # thread cleared between save and regenerate

    llm = _StubFastLLM(response="should not get here")
    service = ChatService(
        bots=None,  # type: ignore[arg-type]
        messages=fake_msgs,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        orchestrator=None,  # type: ignore[arg-type]
        llm=llm,  # type: ignore[arg-type]
    )
    bot = Bot(
        id=1, name="L", personality="", scenario="",
        first_message="", bot_type="rp",
        dynamic_system_prompt="", world_state_prompt="emit",
    )
    request = ConversationRequest(
        thread_id=1, bot_id=1, user_input="hi",
        bot_name="L", bot_personality="", bot_scenario="",
        first_message="", bot_type="rp", history=[], untrusted_context=[],
    )
    # Must not raise.
    await service.regenerate_state(thread_id=1, assistant_message_id=99, bot=bot, request=request)
    # No state was written because the message is gone.
    assert fake_msgs.states == {}
