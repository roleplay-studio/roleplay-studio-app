"""Integration tests for message editing against the real SqlAlchemyMessageRepository.

The unit tests in ``test_message_edit.py`` use a fake ``EditFakeMessageRepo``
that:

  * sorts chronologically ASC (and only via Python after-the-fact);
  * preserves ``is_active`` exactly as passed (no DB filter);
  * stores ``created_at`` from the constructor argument as-is.

The production ``SqlAlchemyMessageRepository.list_for_thread`` does NONE of
that — it sorts DESC, applies a SQL ``branch_group IS NULL OR is_active``
filter, and runs timestamps through ``_ensure_tz`` because SQLite strips
tzinfo. That asymmetry is exactly what allowed the bug Dima reported to
slip through unit tests: "after editing, the old message goes inactive
and the new one never shows up, breaking the message sequence."

This module builds a real ``SqlAlchemyMessageRepository`` against a tmp
SQLite file (mirroring ``test_race_conditions.py``'s integration test)
and exercises the full update_message contract end-to-end.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine as sa_create_engine

from app.application.exceptions import NotFoundError
from app.application.services import ThreadService
from app.infrastructure.config import Settings
from app.infrastructure.db.models import Bot, ChatThread, SQLModel
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyMessageRepository,
    SqlAlchemyStore,
    SqlAlchemyThreadRepository,
)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
async def db_env(tmp_path):
    """Build a fresh SQLite store + repos for one test, tear down after."""
    db = tmp_path / "edit.db"
    settings = Settings(db_path=str(db), _env_file=None)
    store = SqlAlchemyStore(settings=settings)

    # Create schema synchronously (init_db would pull alembic which
    # ignores our per-test db_path).
    sync_engine = sa_create_engine("sqlite:///" + str(db), echo=False)
    SQLModel.metadata.create_all(sync_engine)
    sync_engine.dispose()

    # Seed one bot + one thread.
    async with store._async_session_factory() as s:
        bot = Bot(name="EditBot", personality="", description="", first_message="")
        s.add(bot)
        await s.commit()
        await s.refresh(bot)
        assert bot.id is not None  # narrow for pyright
        thread = ChatThread(bot_id=bot.id, name="edit-thread")
        s.add(thread)
        await s.commit()
        await s.refresh(thread)
        assert thread.id is not None
        thread_id = thread.id

    msgs = SqlAlchemyMessageRepository(store=store)
    threads = SqlAlchemyThreadRepository(store=store)
    service = ThreadService(threads=threads, messages=msgs)

    yield {
        "store": store,
        "messages": msgs,
        "threads": threads,
        "service": service,
        "thread_id": thread_id,
    }

    await store._async_engine.dispose()


# ── Helpers ───────────────────────────────────────────────────────────


async def seed_three(msgs: SqlAlchemyMessageRepository, thread_id: int):
    """Seed [assistant@T0, user@T0+30s, assistant@T0+60s] and return their ids."""
    base = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
    m1 = await msgs.save(thread_id, "assistant", "Hello!", timestamp=base)
    m2 = await msgs.save(thread_id, "user", "Hi bot!", timestamp=base + timedelta(seconds=30))
    m3 = await msgs.save(
        thread_id, "assistant", "How can I help?", timestamp=base + timedelta(seconds=60)
    )
    return m1, m2, m3


def contents(msgs_list) -> list[str]:
    return [m.content for m in msgs_list]


# ══════════════════════════════════════════════════════════════════════
#  THE EXACT BUG Dima reported
# ══════════════════════════════════════════════════════════════════════


class TestReportedBug:
    """The bug as described: "the old message went inactive, the new one
    never appeared, and the sequence broke." We assert the OPPOSITE — that
    the new version DOES appear, at the same position, with the old one
    filtered out of the visible list."""

    async def test_after_edit_new_version_appears_in_list(self, db_env):
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m2 = (await seed_three(msgs, thread_id))[1]

        before = await msgs.list_for_thread(thread_id, limit=50)
        assert contents(before) == ["Hello!", "Hi bot!", "How can I help?"]

        new_id = await service.update_message(thread_id, m2, "Hi there!")

        # Sanity: the service actually returned a new id.
        assert new_id is not None
        assert new_id != m2

        after = await msgs.list_for_thread(thread_id, limit=50)

        # THE KEY ASSERTION: the new version must be visible at m2's slot.
        # If this fails, the bug is back.
        assert len(after) == 3, f"expected 3 messages, got {len(after)}: {contents(after)}"
        assert contents(after) == ["Hello!", "Hi there!", "How can I help?"], (
            f"edit broke the sequence; got {contents(after)}"
        )

    async def test_old_version_filtered_out_of_list(self, db_env):
        """The original (now inactive) message must NOT appear in
        list_for_thread, otherwise we'd see duplicates of 'Hi bot!'
        and 'Hi there!' stacked at the same position."""
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m2 = (await seed_three(msgs, thread_id))[1]

        await service.update_message(thread_id, m2, "Hi there!")

        after = await msgs.list_for_thread(thread_id, limit=50)

        # No duplicate content at the same position.
        assert contents(after) == ["Hello!", "Hi there!", "How can I help?"]
        # Specifically: the OLD content "Hi bot!" must be gone.
        assert "Hi bot!" not in contents(after)

    async def test_sequence_preserved_across_consecutive_edits(self, db_env):
        """Editing the same message twice in a row must keep the visible
        list stable in size and ordering, with only the edited slot's
        content changing."""
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m2 = (await seed_three(msgs, thread_id))[1]

        v1 = await service.update_message(thread_id, m2, "v1")
        v2_id = await service.update_message(thread_id, v1, "v2")
        _ = v2_id

        after = await msgs.list_for_thread(thread_id, limit=50)
        assert len(after) == 3
        assert contents(after) == ["Hello!", "v2", "How can I help?"]


# ══════════════════════════════════════════════════════════════════════
#  Storage-level invariants
# ══════════════════════════════════════════════════════════════════════


class TestStorageInvariants:
    """The DB rows themselves must obey the contract — these checks
    bypass list_for_thread and look at the raw state."""

    async def test_original_marked_inactive_with_branch_index_zero(self, db_env):
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m2 = (await seed_three(msgs, thread_id))[1]

        await service.update_message(thread_id, m2, "edited")

        # The original m2 is still queryable (get_versions looks it up by id
        # via the branch_group on the row), and the version list it returns
        # must include the original with branch_index=0 and is_active=False.
        versions = await msgs.get_versions(m2)
        assert len(versions) == 2
        original = next(v for v in versions if v.id == m2)
        new_version = next(v for v in versions if v.id != m2)
        assert original.branch_index == 0
        assert original.is_active is False
        assert new_version.branch_index == 1
        assert new_version.is_active is True

    async def test_new_version_keeps_original_timestamp(self, db_env):
        """If the new version gets a fresh timestamp (not the original's),
        the message 'slides' to the end of the list — that's how the
        sequence looked broken in the UI. This assertion guards against
        any future refactor that drops the ``timestamp=original_timestamp``
        kwarg."""
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        base = datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC)
        m1 = await msgs.save(thread_id, "assistant", "First", timestamp=base)  # noqa: F841
        m2 = await msgs.save(thread_id, "user", "Second", timestamp=base + timedelta(seconds=30))
        _m3 = await msgs.save(
            thread_id, "assistant", "Third", timestamp=base + timedelta(seconds=60)
        )

        new_id = await service.update_message(thread_id, m2, "Second EDITED")
        assert new_id is not None

        versions = await msgs.get_versions(new_id)
        new_version = next(v for v in versions if v.id == new_id)
        # Original m2 was at base+30s; new version must be at the same time.
        assert new_version.created_at is not None
        original_ts = base + timedelta(seconds=30)
        # Allow tz-naive/aware equivalence — SQLite strips tzinfo on read.
        assert new_version.created_at.replace(tzinfo=UTC) == original_ts

    async def test_only_one_row_visible_per_slot(self, db_env):
        """At the edited slot, exactly one row must survive the
        ``branch_group IS NULL OR is_active`` filter. If two survive
        (e.g. the new version was saved with is_active=False by accident),
        the list would show a duplicate stacked at the same timestamp."""
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m2 = (await seed_three(msgs, thread_id))[1]

        await service.update_message(thread_id, m2, "edited")

        versions = await msgs.get_versions(m2)
        active_in_group = [v for v in versions if v.is_active]
        assert len(active_in_group) == 1
        assert active_in_group[0].content == "edited"

    async def test_other_messages_in_thread_untouched(self, db_env):
        """Editing one message must not affect neighbours' branch fields
        or active flags — they keep branch_group=NULL and is_active=True."""
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m1, m2, m3 = await seed_three(msgs, thread_id)
        # m1, m3 captured for neighbour-field assertions below.

        await service.update_message(thread_id, m2, "edited middle")

        # Re-fetch the whole list (active-only).
        after = await msgs.list_for_thread(thread_id, limit=50)
        m1_dto = next(m for m in after if m.id == m1)
        m3_dto = next(m for m in after if m.id == m3)
        assert m1_dto.branch_group is None
        assert m1_dto.is_active is True
        assert m1_dto.content == "Hello!"
        assert m3_dto.branch_group is None
        assert m3_dto.is_active is True
        assert m3_dto.content == "How can I help?"


# ══════════════════════════════════════════════════════════════════════
#  Edge cases against the real DB
# ══════════════════════════════════════════════════════════════════════


class TestEdgeCasesReal:
    async def test_empty_content_returns_none_and_does_not_branch(self, db_env):
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m2 = (await seed_three(msgs, thread_id))[1]

        result = await service.update_message(thread_id, m2, "   ")
        assert result is None

        after = await msgs.list_for_thread(thread_id, limit=50)
        assert contents(after) == ["Hello!", "Hi bot!", "How can I help?"]
        # m2 must NOT have been moved to a branch group.
        versions = await msgs.get_versions(m2)
        assert versions == []

    async def test_nonexistent_message_raises(self, db_env):
        service = db_env["service"]
        with pytest.raises(NotFoundError):
            await service.update_message(db_env["thread_id"], 999_999, "ghost")

    async def test_three_consecutive_edits_keep_list_size(self, db_env):
        """No matter how many times we edit, the visible list must stay
        the same size — otherwise the chat UI would shift."""
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m2 = (await seed_three(msgs, thread_id))[1]

        v1 = await service.update_message(thread_id, m2, "edit-1")
        v2 = await service.update_message(thread_id, v1, "edit-2")
        _v3 = await service.update_message(thread_id, v2, "edit-3")

        after = await msgs.list_for_thread(thread_id, limit=50)
        assert len(after) == 3
        assert contents(after) == ["Hello!", "edit-3", "How can I help?"]

    async def test_editing_first_message_keeps_it_first(self, db_env):
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        m1, _m2, _m3 = await seed_three(msgs, thread_id)

        await service.update_message(thread_id, m1, "Hello, edited!")

        after = await msgs.list_for_thread(thread_id, limit=50)
        assert contents(after) == ["Hello, edited!", "Hi bot!", "How can I help?"]

    async def test_editing_last_message_keeps_it_last(self, db_env):
        service = db_env["service"]
        msgs = db_env["messages"]
        thread_id = db_env["thread_id"]
        _m1, _m2, m3 = await seed_three(msgs, thread_id)

        await service.update_message(thread_id, m3, "Goodbye, edited!")

        after = await msgs.list_for_thread(thread_id, limit=50)
        assert contents(after) == ["Hello!", "Hi bot!", "Goodbye, edited!"]
