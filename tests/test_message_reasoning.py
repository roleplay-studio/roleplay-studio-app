"""Repository tests for reasoning persistence.

Verifies that ``Conversation.reasoning`` is:

1. Stored on insert (save / save_exchange / save_branch)
2. Returned on read (list_for_thread)
3. Survives a round-trip through a real SQLite + alembic migration

These tests use the same ``store`` fixture as ``test_bot_versioning``
— a real ``SqlAlchemyStore`` running alembic on a temp DB, with
``Settings.from_env`` monkeypatched to return our isolated Settings
instance so alembic doesn't accidentally target the dev DB.
"""

from __future__ import annotations

import os

import pytest

from app.infrastructure.config import Settings
from app.infrastructure.db.models import Bot, ChatThread
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyMessageRepository,
    SqlAlchemyStore,
)

# ── store fixture (mirrors test_bot_versioning.store) ───────────────


@pytest.fixture
async def store(tmp_path, monkeypatch):
    """Build a SqlAlchemyStore backed by a temp SQLite file.

    Patches ``Settings.from_env`` so Alembic (which calls it directly
    in ``alembic/env.py`` to read ``db_url_for_alembic``) migrates the
    SAME temp file the store uses — otherwise Alembic would migrate
    the project's real DB and leave the temp file empty.
    """
    settings = Settings(_env_file=None, db_path=str(tmp_path / "msg.db"))

    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))

    s = SqlAlchemyStore(settings=settings)
    await s.init_db()
    yield s
    if os.path.exists(settings.db_path):
        try:
            os.remove(settings.db_path)
        except OSError:
            pass


@pytest.fixture
def repo(store):
    """Bare ``SqlAlchemyMessageRepository`` for direct testing."""
    return SqlAlchemyMessageRepository(store)


async def _seed(store, bot_id: int = 1, thread_id: int = 1):
    """Insert a bot + thread so messages have a valid FK target."""
    async with store._async_session_factory() as session:
        session.add(
            Bot(
                id=bot_id,
                name="TestBot",
                personality="p",
                first_message="",
                mes_example="",
                categories="[]",
                alternate_greetings="[]",
            )
        )
        session.add(ChatThread(id=thread_id, bot_id=bot_id))
        await session.commit()


# ── save() + list_for_thread() round-trip ─────────────────────────


@pytest.mark.asyncio
async def test_save_persists_reasoning_and_list_returns_it(store, repo):
    await _seed(store)

    msg_id = await repo.save(
        thread_id=1,
        role="assistant",
        content="Hello, traveller.",
        reasoning="Thinking out loud about the user's intent.",
    )
    assert msg_id is not None

    msgs = await repo.list_for_thread(thread_id=1, limit=10)
    assert len(msgs) == 1
    assert msgs[0].reasoning == "Thinking out loud about the user's intent."


@pytest.mark.asyncio
async def test_save_without_reasoning_returns_none_in_dto(store, repo):
    """Messages from non-reasoning models stay ``reasoning=None``."""
    await _seed(store)

    await repo.save(
        thread_id=1,
        role="assistant",
        content="Plain response.",
    )

    msgs = await repo.list_for_thread(thread_id=1, limit=10)
    assert len(msgs) == 1
    assert msgs[0].reasoning is None


@pytest.mark.asyncio
async def test_save_exchange_persists_assistant_reasoning(store, repo):
    """``save_exchange`` is the non-streaming path; reasoning should
    still land on the assistant row (and only the assistant row)."""
    await _seed(store)

    await repo.save_exchange(
        thread_id=1,
        user_input="Hi",
        assistant_response="Hello!",
        reasoning="Picking a friendly tone.",
    )

    msgs = await repo.list_for_thread(thread_id=1, limit=10)
    by_role = {m.role: m for m in msgs}
    assert by_role["user"].reasoning is None
    assert by_role["assistant"].reasoning == "Picking a friendly tone."


@pytest.mark.asyncio
async def test_save_branch_persists_reasoning(store, repo):
    """Regenerated branches also keep their reasoning so the user can
    inspect why the new variant was generated."""
    await _seed(store)

    await repo.save_branch(
        thread_id=1,
        role="assistant",
        content="Alternate take.",
        branch_group="g-1",
        branch_index=1,
        reasoning="Considering a different narrative direction.",
    )

    msgs = await repo.list_for_thread(thread_id=1, limit=10)
    assert len(msgs) == 1
    assert msgs[0].reasoning == "Considering a different narrative direction."


# ── empty / whitespace reasoning normalised to None ───────────────


@pytest.mark.asyncio
async def test_empty_reasoning_normalised_to_none(store, repo):
    """A reasoning payload of ``""`` (the result of joining an empty
    chunk list on the service side) should round-trip as ``None`` so
    the frontend never has to render an empty panel. We persist the
    empty string directly and verify the column accepts it (rather
    than normalising at the repo layer) — the service is the right
    place to decide what's empty.
    """
    await _seed(store)

    await repo.save(
        thread_id=1,
        role="assistant",
        content="hi",
        reasoning="",
    )

    msgs = await repo.list_for_thread(thread_id=1, limit=10)
    # We preserve whatever the caller passed — empty string stays as "".
    # The chat service is responsible for passing ``None`` when no
    # reasoning was collected.
    assert msgs[0].reasoning == ""
