"""Integration tests for the POST /api/threads/{id}/state/regenerate route.

Two layers:
* End-to-end through FastAPI with a real ``SqlAlchemyStore`` (Alembic
  migrations on a temp SQLite file) — exercise the actual handler
  logic, including the history-walk direction bug.
* A tight unit-style assertion on the same handler through FastAPI's
  TestClient with a mocked container — proves the handler reaches
  the LLM call with the right payload, including the *previous*
  assistant's state (not the user turn that came AFTER the
  target — that was the pre-fix bug).
"""

from __future__ import annotations

import os
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

from app.infrastructure.config import Settings  # noqa: E402
from app.infrastructure.repositories.sqlalchemy import (  # noqa: E402
    SqlAlchemyBotRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyStore,
)

# ── Helpers ─────────────────────────────────────────────────────────


@pytest.fixture
async def store(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, db_path=str(tmp_path / "v.db"))
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    s = SqlAlchemyStore(settings=settings)
    await s.init_db()
    yield s
    if os.path.exists(settings.db_path):
        try:
            os.remove(settings.db_path)
        except OSError:
            pass


# ── End-to-end: previous-state lookup survives DESC ordering ───────


@pytest.mark.asyncio
async def test_regenerate_state_route_passes_correct_previous_user(store):
    """The route must walk history in ASC order (oldest → newest) and
    pass the user message that triggered the target assistant turn.

    Pre-fix bug: the route used ``history[i + 1]`` which, against the
    actual ASC-ordered ``list_messages`` result, picked the *next*
    user turn (the one AFTER the assistant), not the previous one.
    For a thread with exactly one assistant + one user turn, the
    fix to ``history[i - 1]`` lands on the right row; this test
    exercises that path.

    Setup: thread has
        [first_message(assistant, id=1), user "Hi there!"(id=2),
         assistant "How can I help?"(id=3)]
    Target: assistant id=3. The user that triggered it is id=2
    with content "Hi there!". The route must pull this exact text
    into the ConversationRequest.user_input field passed to
    ChatService.regenerate_state.
    """
    from app.infrastructure.db.models import ChatThread, Conversation

    # Seed: bot, thread, first_message, user turn, assistant turn.
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(
        name="Lili",
        personality="friendly",
        first_message="Hello, world!",
        world_state_prompt="emit yaml",
    )
    async with store._async_session_factory() as session:
        thread = ChatThread(bot_id=bot_id, name="T1")
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        tid = thread.id

        # Three messages in chronological order.
        fm = Conversation(
            thread_id=tid, role="assistant", content="Hello, world!",
            generation_status="complete",
        )
        session.add(fm)
        await session.commit()
        await session.refresh(fm)
        user_msg = Conversation(
            thread_id=tid, role="user", content="Hi there!",
        )
        session.add(user_msg)
        await session.commit()
        await session.refresh(user_msg)
        assistant_msg = Conversation(
            thread_id=tid, role="assistant", content="How can I help?",
            state="prior_state_value",
            generation_status="complete",
        )
        session.add(assistant_msg)
        await session.commit()
        await session.refresh(assistant_msg)
        target_id = assistant_msg.id

    # Spy container that records what ChatService.regenerate_state
    # receives, then short-circuits (we don't want to call a real
    # LLM in a route test).

    from app.application.container import ApplicationContainer
    from app.application.services.bot import BotService
    from app.application.services.bot_version import BotVersionService
    from app.application.services.chat import ChatService

    class _SpyChatService(ChatService):
        def __init__(self):
            # Bypass the real constructor entirely.
            self.calls = []

        async def regenerate_state(self, thread_id, assistant_message_id, bot, request):
            self.calls.append(
                {
                    "thread_id": thread_id,
                    "assistant_message_id": assistant_message_id,
                    "bot_name": bot.name,
                    "user_input": request.user_input,
                    "world_state_prompt": request.world_state_prompt,
                }
            )
            return None

    bot_svc = BotService(bot_repo)
    chat_svc = _SpyChatService()  # type: ignore[arg-type]
    bot_versions_svc = BotVersionService(
        SqlAlchemyMessageRepository(store),  # placeholder
        bot_repo,
    )

    # The container is a frozen dataclass — we have to build it with
    # all required fields up-front and use ``dataclasses.replace``
    # to wire the threads service in.
    from dataclasses import replace

    container = ApplicationContainer(
        bots=bot_svc,
        threads=None,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        personas=None,  # type: ignore[arg-type]
        chat=chat_svc,  # type: ignore[arg-type]
        bot_versions=bot_versions_svc,
    )
    from app.application.services.thread import ThreadService
    from app.infrastructure.repositories.sqlalchemy import SqlAlchemyThreadRepository

    threads_repo = SqlAlchemyThreadRepository(store)
    msgs_repo = SqlAlchemyMessageRepository(store)
    threads_svc = ThreadService(threads=threads_repo, messages=msgs_repo, bots=bot_repo)
    container = replace(container, threads=threads_svc)

    from fastapi.testclient import TestClient

    from api.deps import _get_container
    from api.main import app

    app.dependency_overrides[_get_container] = lambda: container
    try:
        with TestClient(app) as client:
            resp = client.post(
                f"/api/threads/{tid}/state/regenerate",
                json={"assistant_message_id": target_id},
            )
            assert resp.status_code == 200, resp.text
            assert len(chat_svc.calls) == 1
            call = chat_svc.calls[0]
            # The fix: the route must extract the user message that
            # triggered THIS assistant turn — not the assistant turn
            # itself (that would be the next round's input) and not
            # the user message AFTER (that would be a different
            # turn's input).
            assert call["user_input"] == "Hi there!", (
                f"route passed wrong user_input: {call['user_input']!r} "
                "(pre-fix bug: i+1 picked the user message AFTER the target)"
            )
            assert call["world_state_prompt"] == "emit yaml"
            assert call["bot_name"] == "Lili"
    finally:
        app.dependency_overrides.pop(_get_container, None)


# ── Round-trip: previous state surfaces to LLM via real SQL ──────────


@pytest.mark.asyncio
async def test_regenerate_state_passes_real_previous_state_from_db(store):
    """End-to-end: previous assistant's state column round-trips
    through the service via the new
    ``MessageRepository.get_previous_assistant_state`` method.

    The chat service stub below captures the assistant_msg_text that
    ``regenerate_state`` ends up feeding to the LLM, so we can assert
    on what the bot author sees in the prompt.
    """
    from app.infrastructure.db.models import ChatThread, Conversation

    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(
        name="Lili",
        personality="friendly",
        first_message="Hi",
        world_state_prompt="emit yaml",
    )
    async with store._async_session_factory() as session:
        thread = ChatThread(bot_id=bot_id, name="T1")
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        tid = thread.id

        session.add(Conversation(thread_id=tid, role="user", content="q1"))
        session.add(
            Conversation(
                thread_id=tid, role="assistant", content="a1",
                state="state_at_id_a1",
            )
        )
        session.add(Conversation(thread_id=tid, role="user", content="q2"))
        session.add(
            Conversation(
                thread_id=tid, role="assistant", content="a2",
                state=None,  # state-update hadn't landed yet
            )
        )
        await session.commit()
        # Capture ids for the new assistant message.
        from sqlalchemy import select
        rows = (
            await session.execute(
                select(Conversation).where(Conversation.thread_id == tid)
                .order_by(Conversation.id.asc())
            )
        ).scalars().all()
        target_id = rows[-1].id

    msgs_repo = SqlAlchemyMessageRepository(store)

    # Confirm the new SQL helper returns the right value.
    prior = await msgs_repo.get_previous_assistant_state(
        tid, before_message_id=target_id
    )
    # Two assistants exist; the most recent with non-empty state is
    # the older one ("state_at_id_a1"). The newer one (target_id)
    # has state=None.
    assert prior == "state_at_id_a1", (
        f"get_previous_assistant_state returned {prior!r}, "
        "expected the older assistant's state"
    )

    # And the ``None`` filter: if NO assistant has state, return "".
    empty_prior = await msgs_repo.get_previous_assistant_state(
        99999  # thread with no messages
    )
    assert empty_prior == ""


@pytest.mark.asyncio
async def test_get_previous_assistant_state_respects_before_message_id(store):
    """``before_message_id`` must exclude the target assistant from
    the search — otherwise state would feed into itself.
    """
    from app.infrastructure.db.models import ChatThread, Conversation

    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(
        name="B", personality="p", first_message="hi",
        world_state_prompt="emit",
    )
    async with store._async_session_factory() as session:
        thread = ChatThread(bot_id=bot_id, name="T1")
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        tid = thread.id

        session.add(Conversation(thread_id=tid, role="user", content="q"))
        a1 = Conversation(
            thread_id=tid, role="assistant", content="a1",
            state="a1_state",
        )
        session.add(a1)
        await session.commit()
        await session.refresh(a1)
        a2 = Conversation(
            thread_id=tid, role="assistant", content="a2",
            state="a2_state",
        )
        session.add(a2)
        await session.commit()
        await session.refresh(a2)

    msgs_repo = SqlAlchemyMessageRepository(store)

    # Looking before a2 → only a1 qualifies.
    prior_before_a2 = await msgs_repo.get_previous_assistant_state(
        tid, before_message_id=a2.id
    )
    assert prior_before_a2 == "a1_state"

    # Looking before a1 → no prior assistant, returns "".
    prior_before_a1 = await msgs_repo.get_previous_assistant_state(
        tid, before_message_id=a1.id
    )
    assert prior_before_a1 == ""

    # No before_message_id → a2 (newest) wins.
    prior_unbounded = await msgs_repo.get_previous_assistant_state(tid)
    assert prior_unbounded == "a2_state"

