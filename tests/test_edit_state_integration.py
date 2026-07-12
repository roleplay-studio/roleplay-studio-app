"""Integration test for the new ``state`` plumbing through edit+branch.

The unit suite covers the service contract with a fake repo; this file
exercises the *real* SqlAlchemyMessageRepository on top of the real
SqlAlchemyStore + Alembic, hitting the same column-mapping pitfalls
that AGENTS.md §2 ("fake repos mask bugs") warns about.

Covers:

1. ``save`` round-trips ``state`` through to the SQL row (NULL →
   value → cleared).
2. Branching via ``save_branch`` carries state to the new active
   row, even when the original message had state populated by
   ``regenerate_state``.
3. Re-reading via ``list_for_thread`` projects ``state`` back out
   for both original and branch.

Without this, the SQL repo's lack of ``state`` kwarg would have been
caught only by a runtime surprise — which is exactly the multi-layer
wiring regression AGENTS.md §2 insists we test against.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

for mod in [
    "langgraph",
    "langgraph.graph",
    "langchain_openai",
    "langchain_core",
    "langchain_core.messages",
    "langchain_community",
    "langchain_chroma",
]:
    sys.modules.setdefault(mod, MagicMock())


from app.infrastructure.config import Settings  # noqa: E402
from app.infrastructure.repositories.sqlalchemy import (  # noqa: E402
    SqlAlchemyBotRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyStore,
    SqlAlchemyThreadRepository,
)


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


async def _seed_thread_with_assistant_state(store, state_value):
    """Create bot+thread, then one assistant row with ``state_value``.

    Returns the (bot_id, thread_id, message_id) tuple.
    """
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(
        name="t",
        personality="calm",
        first_message="x",
        bot_type="RolePlay",
    )
    thread_repo = SqlAlchemyThreadRepository(store)
    thread_id = await thread_repo.create(bot_id=bot_id, name="t")

    msg_repo = SqlAlchemyMessageRepository(store)
    mid = await msg_repo.save(
        thread_id=thread_id,
        role="assistant",
        content="assistant turn 1",
        state=state_value,
    )
    return bot_id, thread_id, mid


# ── save() round-trips state ──────────────────────────────────────


async def test_save_round_trips_state_through_sql(store):
    """``save(state=X)`` persists ``X`` and the column survives a
    re-read through ``list_for_thread``.
    """
    _, tid, mid = await _seed_thread_with_assistant_state(store, state_value="world: rainy")

    msgs = await SqlAlchemyMessageRepository(store).list_for_thread(tid)
    target = next(m for m in msgs if m.id == mid)

    assert target.state == "world: rainy"


async def test_save_with_state_none_leaves_column_null(store):
    """Default ``state=None`` keeps the column NULL — matches the
    historical behaviour for pre-state-update assistant rows and
    user messages which never had a state.
    """
    _, tid, mid = await _seed_thread_with_assistant_state(store, state_value=None)

    msgs = await SqlAlchemyMessageRepository(store).list_for_thread(tid)
    target = next(m for m in msgs if m.id == mid)

    assert target.state is None


async def test_save_with_state_empty_string_persists_empty(store):
    """Empty string ``""`` is a deliberate "clear" — distinct from
    NULL. The frontend ``EditMessageModal`` sends ``""`` when the
    state textarea is empty; this must round-trip as ``""``, not NULL.
    """
    _, tid, mid = await _seed_thread_with_assistant_state(store, state_value="")

    msgs = await SqlAlchemyMessageRepository(store).list_for_thread(tid)
    target = next(m for m in msgs if m.id == mid)

    # Empty string lands in the DB as empty string, not NULL.
    assert target.state == ""


# ── save_branch() flows state ─────────────────────────────────────


async def test_save_branch_with_state_round_trips(store):
    """``save_branch(state=X)`` persists ``X`` on the new row.
    Without this assertion, the AGENTS.md §2 "triple-step change"
    trap would still bite: protocol accepts state, service passes it,
    but the SQL repo silently drops it.
    """
    _, tid, _orig = await _seed_thread_with_assistant_state(
        store, state_value="snapshot-on-original"
    )

    repo = SqlAlchemyMessageRepository(store)
    branch_id = await repo.save_branch(
        thread_id=tid,
        role="assistant",
        content="branch content",
        branch_group="bg-integration",
        branch_index=1,
        state="snapshot-on-branch",
    )
    assert branch_id is not None

    msgs = await repo.list_for_thread(tid)
    branch = next(m for m in msgs if m.id == branch_id)

    assert branch.state == "snapshot-on-branch"


async def test_save_branch_without_state_leaves_null(store):
    """Default ``state=None`` on ``save_branch`` is the legacy path
    (used by code paths that don't yet plumb state through — keeps
    backward compat for the original MessageRepository.save_exchange).
    """
    _, tid, _orig = await _seed_thread_with_assistant_state(store, state_value="ignored")

    repo = SqlAlchemyMessageRepository(store)
    branch_id = await repo.save_branch(
        thread_id=tid,
        role="assistant",
        content="branch with default null state",
        branch_group="bg-null",
        branch_index=1,
    )

    msgs = await repo.list_for_thread(tid)
    branch = next(m for m in msgs if m.id == branch_id)
    assert branch.state is None
