"""Tests for active-branch filtering in
``SqlAlchemyMessageRepository.get_previous_assistant_state``.

Catches the regression where ``get_previous_assistant_state`` would
return the most recent non-empty assistant state across **all**
rows in the thread, regardless of ``is_active`` / ``branch_group``
membership. After a regenerate / retry the prior assistant
message is deactivated (``is_active=False``) and a new
``branch_group`` is created — without the active-branch filter,
``get_previous_assistant_state`` would happily hand back a state
from the dead branch and the state-update regenerator would
hallucinate a world-state carryover that doesn't match what's
actually on screen.

Why an integration test: the SQL behaviour is the contract;
fakes would re-implement the bug at the same level of confidence
as the production code. Round-trip through real SQLite + Alembic
+ the actual ``Conversation`` model.
"""

from __future__ import annotations

import os

# Mirror the sys.modules dance from test_state_propagation.py so
# the test can import the chat service without dragging in real
# langgraph / langchain / chroma modules.
import sys
from unittest.mock import MagicMock

sys.modules.setdefault("langgraph", MagicMock())
sys.modules.setdefault("langgraph.graph", MagicMock())
sys.modules.setdefault("langchain_openai", MagicMock())
sys.modules.setdefault("langchain_core", MagicMock())
sys.modules.setdefault("langchain_core.messages", MagicMock())
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_chroma", MagicMock())

import pytest  # noqa: E402

from app.infrastructure.config import Settings  # noqa: E402
from app.infrastructure.repositories.sqlalchemy import (  # noqa: E402
    SqlAlchemyBotRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyStore,
    SqlAlchemyThreadRepository,
)


@pytest.fixture
async def ctx(tmp_path, monkeypatch):
    """Build a fresh SqlAlchemy-backed test environment.

    Returns a ``ctx`` namespace with a bot id, thread id, the
    message repo, and the session factory — enough to seed
    branch-aware assistant messages and run the
    ``get_previous_assistant_state`` query.
    """
    settings = Settings(_env_file=None, db_path=str(tmp_path / "v.db"))
    monkeypatch.setattr(
        "app.infrastructure.config.Settings.from_env",
        classmethod(lambda cls: settings),
    )
    s = SqlAlchemyStore(settings=settings)
    await s.init_db()

    bot_repo = SqlAlchemyBotRepository(s)
    bot_id = await bot_repo.create(
        name="Lili",
        personality="friendly",
        first_message="hi",
        world_state_prompt="emit yaml",
        dynamic_system_prompt="",
    )

    threads_repo = SqlAlchemyThreadRepository(s)
    tid = await threads_repo.create(bot_id=bot_id, name="T1")

    msgs_repo = SqlAlchemyMessageRepository(s)
    yield msgs_repo, tid, s._async_session_factory

    if os.path.exists(settings.db_path):
        try:
            os.remove(settings.db_path)
        except OSError:
            pass


@pytest.mark.asyncio
async def test_get_previous_state_skips_inactive_branch(ctx) -> None:
    """The classic bug: after a regenerate, the previous
    assistant turn is deactivated. ``get_previous_assistant_state``
    must NOT return its state — the regenerator must start from
    the active chain.
    """
    msgs_repo, thread_id, session_factory = ctx

    # Seed: two assistant messages in the same thread, one
    # active and one explicitly inactive (mimicking a
    # regenerate that deactivated the prior turn). The active
    # one has a tiny placeholder state, the inactive one has a
    # big YAML state — if the SQL doesn't filter, the inactive
    # one wins by id (it's later in the table) and the test
    # catches it.
    active_state = "```yaml\nuser:\n  health: 90\n```"
    inactive_state = (
        "```yaml\nuser:\n  health: 999\n  stale: 1\n" + ("padding " * 200) + "\n```"
    )

    async with session_factory() as session:
        from app.infrastructure.db.models import Conversation

        active = Conversation(
            thread_id=thread_id,
            role="assistant",
            content="active assistant reply",
            state=active_state,
            branch_group="bg_active",
            branch_index=0,
            is_active=True,
        )
        session.add(active)
        await session.flush()
        active_id = active.id

        inactive = Conversation(
            thread_id=thread_id,
            role="assistant",
            content="inactive assistant reply (regenerated away)",
            state=inactive_state,
            branch_group="bg_stale",
            branch_index=0,
            is_active=False,
        )
        session.add(inactive)
        await session.flush()
        inactive_id = inactive.id
        await session.commit()

    # Sanity: inactive is later in the id sequence — the
    # pre-fix ORDER BY id DESC would pick it.
    assert inactive_id > active_id, (
        "Test setup error: inactive message must have a higher id "
        "than the active one to exercise the filter"
    )

    found = await msgs_repo.get_previous_assistant_state(thread_id)
    assert found == active_state, (
        f"get_previous_assistant_state leaked state from inactive "
        f"branch (id={inactive_id}, is_active=False). "
        f"Got {found!r}, expected the active-branch state {active_state!r}."
    )


@pytest.mark.asyncio
async def test_get_previous_state_treats_legacy_rows_as_active(ctx) -> None:
    """Pre-branching rows (branch_group IS NULL) are the trunk —
    they're always considered part of the active chain. The
    filter must not exclude them just because they predate the
    branching system.
    """
    msgs_repo, thread_id, session_factory = ctx

    legacy_state = "```yaml\nuser:\n  health: 50\n```"

    async with session_factory() as session:
        from app.infrastructure.db.models import Conversation

        legacy = Conversation(
            thread_id=thread_id,
            role="assistant",
            content="legacy assistant reply (no branch_group)",
            state=legacy_state,
            branch_group=None,  # pre-branching trunk
            branch_index=0,
            is_active=True,
        )
        session.add(legacy)
        await session.commit()

    found = await msgs_repo.get_previous_assistant_state(thread_id)
    assert found == legacy_state, (
        f"Pre-branching legacy state was filtered out: got {found!r}, "
        f"expected {legacy_state!r}"
    )


@pytest.mark.asyncio
async def test_get_previous_state_returns_empty_when_only_inactive(ctx) -> None:
    """If every assistant state in the thread is on an inactive
    branch, the helper must return ``""`` — not the most recent
    inactive state. The regenerator should start from scratch
    rather than hallucinating a carryover.
    """
    msgs_repo, thread_id, session_factory = ctx

    async with session_factory() as session:
        from app.infrastructure.db.models import Conversation

        for i in range(3):
            session.add(
                Conversation(
                    thread_id=thread_id,
                    role="assistant",
                    content=f"inactive #{i}",
                    state=f"```yaml\nuser:\n  health: {i}\n```",
                    branch_group=f"bg_{i}",
                    branch_index=0,
                    is_active=False,
                )
            )
        await session.commit()

    found = await msgs_repo.get_previous_assistant_state(thread_id)
    assert found == "", (
        f"All-assistants-inactive should return empty state, got {found!r}"
    )


@pytest.mark.asyncio
async def test_get_previous_state_picks_active_when_mixed(ctx) -> None:
    """Mixed: several inactive rows + one active row, in any id
    order. The active one must win.
    """
    msgs_repo, thread_id, session_factory = ctx
    active_state = "```yaml\nuser:\n  health: 77\n```"

    async with session_factory() as session:
        from app.infrastructure.db.models import Conversation

        # Three inactive rows
        for i in range(3):
            session.add(
                Conversation(
                    thread_id=thread_id,
                    role="assistant",
                    content=f"inactive #{i}",
                    state=f"```yaml\ninactive: {i}\n```",
                    branch_group=f"bg_inactive_{i}",
                    branch_index=0,
                    is_active=False,
                )
            )
        # One active row, intentionally inserted last so it has
        # the highest id.
        session.add(
            Conversation(
                thread_id=thread_id,
                role="assistant",
                content="active",
                state=active_state,
                branch_group="bg_active_only",
                branch_index=0,
                is_active=True,
            )
        )
        await session.commit()

    found = await msgs_repo.get_previous_assistant_state(thread_id)
    assert found == active_state
