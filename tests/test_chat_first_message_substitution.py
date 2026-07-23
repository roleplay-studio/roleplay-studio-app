"""Regression tests for ``{{user}}`` substitution in saved messages.

The orchestrator's ``_variable_replace`` substitutes ``{{user}}`` /
``{{char}}`` placeholders for the current user persona name /
bot name on every prompt assembly. The catch: ``stream_save_first_message``
saves ``bot.first_message`` to the DB **before** the orchestrator
gets a chance to substitute — so the literal ``{{user}}`` token
ends up persisted. On subsequent turns the rebuilt history
serves that DB row back to the LLM with the placeholder still
present, and any future ``regenerate`` / ``retry`` reads the
un-substituted text from the DB.

The fix: ``stream_save_first_message`` now takes the persona
name (when available) and substitutes ``{{user}}`` inline before
the ``save_first_assistant_if_absent`` call. ``ChatService.stream_message``
resolves the persona up front and passes the name through.
"""
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.application.services.chat import ChatService

# ── Minimal fakes (mirrors test_chat_generation.py patterns) ─────


class FakeBotRepo:
    def __init__(self) -> None:
        self._bots: dict[int, dict] = {}
        self._next_id = 1

    async def create(
        self,
        name: str,
        first_message: str = "",
        **kwargs: Any,
    ) -> int:
        bid = self._next_id
        self._next_id += 1
        self._bots[bid] = {
            "id": bid,
            "name": name,
            "first_message": first_message,
            "scenario": "",
            "description": "",
            "avatar_path": None,
            "categories": [],
            "bot_type": "rp",
            "mes_example": "",
            "personality": "friendly",
            **kwargs,
        }
        return bid

    async def get(self, bot_id: int) -> SimpleNamespace | None:
        data = self._bots.get(bot_id)
        return SimpleNamespace(**data) if data else None


class FakeMessagesRepo:
    """In-memory message repo that records what got saved.

    Mirrors the production ``save_first_assistant_if_absent`` contract:
    stores the row on the first call for a thread and returns True;
    subsequent calls return False without inserting.
    """

    def __init__(self) -> None:
        self.first_messages: dict[int, str] = {}

    async def save_first_assistant_if_absent(
        self, thread_id: int, content: str
    ) -> bool:
        if thread_id in self.first_messages:
            return False
        self.first_messages[thread_id] = content
        return True


class FakeKnowledgeRepo:
    async def has_documents(self, bot_id: int) -> bool:
        return False


class FakePersonaRepo:
    """Returns a fixed persona by id."""

    def __init__(self, personas: dict[int, SimpleNamespace]) -> None:
        self._personas = personas

    async def get(self, persona_id: int) -> SimpleNamespace | None:
        return self._personas.get(persona_id)


class FakeOrchestrator:
    def __init__(self) -> None:
        self.last_request: Any = None

    async def generate_stream(self, request):
        self.last_request = request
        yield type(
            "Chunk",
            (),
            {"content": "", "reasoning": None, "usage": None, "debug_messages": None},
        )()


# ── Direct unit tests for stream_save_first_message ────────────────


@pytest.mark.asyncio
async def test_first_message_substitutes_user_placeholder() -> None:
    """When a persona name is provided, ``{{user}}`` is replaced
    in the persisted text — every occurrence, not just the first.
    """
    bots = FakeBotRepo()
    bot_id = await bots.create(
        name="Kira",
        first_message=(
            "Hi {{user}}! Welcome back, {{user}}. "
            "I missed you, {{user}}."
        ),
    )
    msgs = FakeMessagesRepo()
    service = ChatService(
        bots,  # type: ignore[arg-type]
        msgs,  # type: ignore[arg-type]
        FakeKnowledgeRepo(),  # type: ignore[arg-type]
        FakeOrchestrator(),  # type: ignore[arg-type]
    )

    await service.stream_save_first_message(
        thread_id=1, bot_id=bot_id, persona_name="Alice"
    )

    assert msgs.first_messages[1] == (
        "Hi Alice! Welcome back, Alice. I missed you, Alice."
    )


@pytest.mark.asyncio
async def test_first_message_without_persona_leaves_placeholder_alone() -> None:
    """When no persona is selected, the literal ``{{user}}`` token
    is preserved — the orchestrator's ``_variable_replace`` will
    handle it on the first turn, and a later ``regenerate`` /
    persona change can still substitute without the user name
    being baked into the saved row.
    """
    bots = FakeBotRepo()
    bot_id = await bots.create(
        name="Kira",
        first_message="Hi {{user}}!",
    )
    msgs = FakeMessagesRepo()
    service = ChatService(
        bots,  # type: ignore[arg-type]
        msgs,  # type: ignore[arg-type]
        FakeKnowledgeRepo(),  # type: ignore[arg-type]
        FakeOrchestrator(),  # type: ignore[arg-type]
    )

    await service.stream_save_first_message(
        thread_id=1, bot_id=bot_id, persona_name=None
    )

    assert msgs.first_messages[1] == "Hi {{user}}!"


@pytest.mark.asyncio
async def test_first_message_with_empty_persona_name_keeps_placeholder() -> None:
    """An empty persona name (caller forgot to pass it) must NOT
    trigger a wholesale ``str.replace`` that wipes the placeholder
    with an empty string. The placeholder survives — better to
    let the LLM see ``{{user}}`` than to lose the name entirely.
    """
    bots = FakeBotRepo()
    bot_id = await bots.create(
        name="Kira",
        first_message="Hi {{user}}!",
    )
    msgs = FakeMessagesRepo()
    service = ChatService(
        bots,  # type: ignore[arg-type]
        msgs,  # type: ignore[arg-type]
        FakeKnowledgeRepo(),  # type: ignore[arg-type]
        FakeOrchestrator(),  # type: ignore[arg-type]
    )

    await service.stream_save_first_message(
        thread_id=1, bot_id=bot_id, persona_name=""
    )

    assert msgs.first_messages[1] == "Hi {{user}}!"


@pytest.mark.asyncio
async def test_first_message_without_placeholder_passes_through_unchanged() -> None:
    """When ``bot.first_message`` has no ``{{user}}`` token, the
    call is a no-op for substitution — the text is still saved
    verbatim (no spurious transformations).
    """
    bots = FakeBotRepo()
    bot_id = await bots.create(
        name="Kira",
        first_message="Welcome to the tavern, friend.",
    )
    msgs = FakeMessagesRepo()
    service = ChatService(
        bots,  # type: ignore[arg-type]
        msgs,  # type: ignore[arg-type]
        FakeKnowledgeRepo(),  # type: ignore[arg-type]
        FakeOrchestrator(),  # type: ignore[arg-type]
    )

    await service.stream_save_first_message(
        thread_id=1, bot_id=bot_id, persona_name="Alice"
    )

    assert msgs.first_messages[1] == "Welcome to the tavern, friend."


# ── End-to-end: ChatService.stream_message resolves persona name
#    and passes it to stream_save_first_message ─────────────────────


@pytest.mark.asyncio
async def test_stream_message_passes_resolved_persona_name() -> None:
    """``ChatService.stream_message`` resolves the user persona
    (if any) BEFORE calling ``stream_save_first_message`` and
    passes the name through. We patch ``stream_save_first_message``
    on the instance so we can observe the call without having
    to build out the full streaming pipeline.
    """
    bots = FakeBotRepo()
    bot_id = await bots.create(
        name="Kira",
        first_message="Hi {{user}}, I'm {{user}}'s friend.",
    )
    personas = FakePersonaRepo(
        {7: SimpleNamespace(id=7, name="Bob", description="")}
    )
    service = ChatService(
        bots,  # type: ignore[arg-type]
        FakeMessagesRepo(),  # type: ignore[arg-type]
        FakeKnowledgeRepo(),  # type: ignore[arg-type]
        FakeOrchestrator(),  # type: ignore[arg-type]
        personas=personas,  # type: ignore[arg-type]
    )

    captured: dict[str, Any] = {}

    async def spy_save_first_message(
        thread_id: int, bot_id: int, persona_name: str | None = None
    ) -> None:
        captured["thread_id"] = thread_id
        captured["bot_id"] = bot_id
        captured["persona_name"] = persona_name

    service.stream_save_first_message = spy_save_first_message  # type: ignore[method-assign]

    # ``stream_message`` is an async generator — must be iterated
    # via ``async for`` to actually run its body. We swallow the
    # exception from the half-faked LLM path that comes after
    # the first-message save; the test only cares that the
    # persona resolution happened before the save.
    try:
        async for _ in service.stream_message(
            SimpleNamespace(  # type: ignore[arg-type]
                thread_id=1,
                bot_id=bot_id,
                user_input="hello",
                persona_id=7,
                file_ids=[],
            )
        ):
            pass
    except Exception:
        pass

    # The persona name MUST be resolved and passed in.
    assert captured.get("persona_name") == "Bob", (
        f"stream_save_first_message should receive the resolved persona "
        f"name 'Bob', got {captured.get('persona_name')!r}"
    )


@pytest.mark.asyncio
async def test_stream_message_passes_none_persona_when_no_persona_selected() -> None:
    """When no persona is selected (``command.persona_id is None``
    or the persona repo returns ``None``), the persona_name
    passed to ``stream_save_first_message`` is ``None`` — the
    placeholder survives in the DB and the orchestrator handles
    it on the first turn.
    """
    bots = FakeBotRepo()
    bot_id = await bots.create(
        name="Kira",
        first_message="Hi {{user}}!",
    )
    service = ChatService(
        bots,  # type: ignore[arg-type]
        FakeMessagesRepo(),  # type: ignore[arg-type]
        FakeKnowledgeRepo(),  # type: ignore[arg-type]
        FakeOrchestrator(),  # type: ignore[arg-type]
    )

    captured: dict[str, Any] = {}

    async def spy_save_first_message(
        thread_id: int, bot_id: int, persona_name: str | None = None
    ) -> None:
        captured["persona_name"] = persona_name

    service.stream_save_first_message = spy_save_first_message  # type: ignore[method-assign]

    try:
        async for _ in service.stream_message(
            SimpleNamespace(  # type: ignore[arg-type]
                thread_id=1,
                bot_id=bot_id,
                user_input="hello",
                persona_id=None,
                file_ids=[],
            )
        ):
            pass
    except Exception:
        pass

    assert captured.get("persona_name") is None
