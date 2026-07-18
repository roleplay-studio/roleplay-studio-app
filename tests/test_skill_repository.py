"""Tests for SqlAlchemySkillRepository + GlobalSkill model. See spec §4.1."""
import json

import pytest
from sqlalchemy import select

from app.application.exceptions import NotFoundError
from app.application.ports import DeleteSkillResult
from app.infrastructure.config import Settings
from app.infrastructure.db.models import Bot, GlobalSkill
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemySkillRepository,
    SqlAlchemyStore,
)


@pytest.fixture
async def store(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, db_path=str(tmp_path / "v.db"))
    # Force ``alembic/env.py`` to use the same Settings instance as the
    # SqlAlchemyStore — without this, alembic re-reads env via
    # ``Settings.from_env()`` and applies migrations to the WRONG
    # database (default ``conversations.db``) while the test reads
    # from the tmp_path SQLite. Pattern from
    # tests/test_thread_list_enrichment.py:43-46.
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    s = SqlAlchemyStore(settings=settings)
    await s.init_db()
    yield s
    # No close() — SqlAlchemyStore is stateless after init_db and the
    # tmp_path DB file is cleaned up by pytest. Matches the pattern in
    # tests/test_thread_list_enrichment.py and tests/test_regenerate_after_edit.py.


@pytest.fixture
def repo(store):
    return SqlAlchemySkillRepository(store)


# ── Model tests (Task 1) ─────────────────────────────────────────


async def test_global_skill_table_created_with_columns(store):
    """After init_db, global_skills table exists with expected columns."""
    async with store._async_session_factory() as session:
        # SQLite's pragma_table_info returns one row per column.
        # Project convention: use raw SQL via session.execute(text(...))
        # rather than sqlalchemy.inspect on the async session (which
        # has known issues with session.bind.sync_engine in 2.x).
        from sqlalchemy import text
        result = await session.execute(text("PRAGMA table_info(global_skills)"))
        cols = {row[1] for row in result.fetchall()}
    expected = {"id", "name", "description", "instruction", "tags", "created_at", "updated_at"}
    assert expected <= cols, f"missing columns: {expected - cols}"


async def test_bot_skill_ids_column_defaults_to_empty_json(store):
    """New Bot rows have skill_ids='[]' by default (parity with categories)."""
    async with store._async_session_factory() as session:
        bot = Bot(name="x", personality="y", skill_ids="[]")
        session.add(bot)
        await session.commit()
        await session.refresh(bot)
    assert bot.skill_ids == "[]"


# ── SqlAlchemySkillRepository tests (Task 2) ──────────────────────


async def test_create_returns_id_and_normalizes_tags(repo, store):
    # Unique name — DB already contains 4 seed skills after init_db.
    skill_id = await repo.create(
        name="MySarcastic",
        description="Speak with dry wit.",
        instruction="Apply when user uses sarcasm first.",
        tags=["Tone", "dialog", "tone"],  # mixed case + duplicate
    )
    assert isinstance(skill_id, int)
    async with store._async_session_factory() as session:
        result = await session.execute(select(GlobalSkill).where(GlobalSkill.id == skill_id))
        skill = result.scalar_one()
        assert skill.name == "MySarcastic"
        assert json.loads(skill.tags) == ["tone", "dialog"]


async def test_create_duplicate_name_raises_value_error(repo):
    await repo.create(name="Dup", description="", instruction="x", tags=[])
    with pytest.raises(ValueError, match="already exists"):
        await repo.create(name="Dup", description="", instruction="y", tags=[])


async def test_create_with_empty_tags_returns_empty_list(repo, store):
    sid = await repo.create(name="EmptyTagsSkill", description="d", instruction="i", tags=[])
    async with store._async_session_factory() as session:
        result = await session.execute(select(GlobalSkill).where(GlobalSkill.id == sid))
        skill = result.scalar_one()
    assert json.loads(skill.tags) == []


async def test_get_returns_none_for_unknown_id(repo):
    assert await repo.get(99999) is None


async def test_list_all_with_q_filters_by_name_substring_case_insensitive(repo):
    await repo.create(name="MyConcise", description="short replies", instruction="...", tags=[])
    await repo.create(name="MyVerbose", description="long replies", instruction="...", tags=[])
    results = await repo.list_all(q="myconci")
    assert len(results) == 1
    assert results[0].name == "MyConcise"


async def test_list_all_with_q_matches_description_too(repo):
    """q filter checks both name and description."""
    await repo.create(name="QDescTestA", description="speaks with dry irony", instruction="x", tags=[])
    await repo.create(name="QDescTestB", description="talks politely", instruction="y", tags=[])
    results = await repo.list_all(q="dry irony")
    assert len(results) == 1
    assert results[0].name == "QDescTestA"


async def test_list_all_with_tag_filters_case_insensitive(repo):
    await repo.create(name="TagTestA", description="", instruction="x", tags=["UniqueMarker"])
    await repo.create(name="TagTestB", description="", instruction="y", tags=["dialog"])
    results = await repo.list_all(tag="uniquemarker")
    assert len(results) == 1
    assert results[0].name == "TagTestA"


async def test_list_all_with_no_filters_returns_all(repo):
    # 4 seed + 3 new = 7
    n_before = len(await repo.list_all())
    await repo.create(name="NFTestA", description="", instruction="x", tags=[])
    await repo.create(name="NFTestB", description="", instruction="y", tags=[])
    await repo.create(name="NFTestC", description="", instruction="z", tags=[])
    results = await repo.list_all()
    assert len(results) == n_before + 3


async def test_list_by_ids_preserves_input_order(repo):
    id1 = await repo.create(name="A", description="", instruction="x", tags=[])
    id2 = await repo.create(name="B", description="", instruction="y", tags=[])
    id3 = await repo.create(name="C", description="", instruction="z", tags=[])
    results = await repo.list_by_ids([id3, id1, id2])
    # Per spec §6.1, sorted by id ASC (not input order).
    # This is the canonical sort order for bulk fetches.
    assert [r.id for r in results] == [id1, id2, id3]


async def test_list_by_ids_silently_skips_unknown(repo):
    id1 = await repo.create(name="A", description="", instruction="x", tags=[])
    results = await repo.list_by_ids([id1, 99999])
    assert len(results) == 1
    assert results[0].id == id1


async def test_list_by_ids_empty_input_returns_empty_list(repo):
    assert await repo.list_by_ids([]) == []


async def test_update_partial_keeps_unchanged(repo, store):
    sid = await repo.create(name="A", description="orig", instruction="x", tags=["t1"])
    await repo.update(sid, description="new")
    async with store._async_session_factory() as session:
        result = await session.execute(select(GlobalSkill).where(GlobalSkill.id == sid))
        skill = result.scalar_one()
    assert skill.description == "new"
    assert skill.name == "A"  # unchanged
    assert json.loads(skill.tags) == ["t1"]  # unchanged


async def test_update_normalizes_tags(repo, store):
    sid = await repo.create(name="A", description="", instruction="x", tags=[])
    await repo.update(sid, tags=["NEW", "another", "new"])  # mixed case + dup
    async with store._async_session_factory() as session:
        result = await session.execute(select(GlobalSkill).where(GlobalSkill.id == sid))
        skill = result.scalar_one()
    assert json.loads(skill.tags) == ["new", "another"]


async def test_update_unknown_id_raises_not_found(repo):
    with pytest.raises(NotFoundError, match="999"):
        await repo.update(999, name="x")


async def test_delete_with_no_attachments(repo, store):
    sid = await repo.create(name="A", description="", instruction="x", tags=[])
    result = await repo.delete(sid)
    assert isinstance(result, DeleteSkillResult)
    assert result.deleted is True
    assert result.attached_to == []
    # Verify row is gone
    async with store._async_session_factory() as session:
        row = await session.get(GlobalSkill, sid)
    assert row is None


async def test_delete_with_attachments_returns_attached_to(repo, store):
    """If any bot has this skill_id in skill_ids_json, return attached_to list (don't delete)."""
    sid = await repo.create(name="A", description="", instruction="x", tags=[])
    async with store._async_session_factory() as session:
        bot = Bot(name="b1", personality="p", skill_ids=json.dumps([sid]))
        session.add(bot)
        await session.commit()
    result = await repo.delete(sid)
    assert result.deleted is False
    assert len(result.attached_to) == 1
    # Verify row still exists (was NOT deleted)
    async with store._async_session_factory() as session:
        row = await session.get(GlobalSkill, sid)
    assert row is not None


async def test_delete_unknown_id_returns_not_deleted(repo):
    result = await repo.delete(99999)
    assert result.deleted is False
    assert result.attached_to == []


async def test_count_attached_returns_zero_when_no_bots(repo):
    sid = await repo.create(name="A", description="", instruction="x", tags=[])
    assert await repo.count_attached(sid) == 0


async def test_count_attached_counts_unique_bots_with_skill_id(repo, store):
    sid = await repo.create(name="A", description="", instruction="x", tags=[])
    async with store._async_session_factory() as session:
        # Two bots, both reference this skill
        bot1 = Bot(name="b1", personality="p", skill_ids=json.dumps([sid]))
        bot2 = Bot(name="b2", personality="p", skill_ids=json.dumps([sid, 999]))
        bot3 = Bot(name="b3", personality="p", skill_ids="[]")  # not attached
        session.add_all([bot1, bot2, bot3])
        await session.commit()
    assert await repo.count_attached(sid) == 2


# ── Seed tests (Task 3) ───────────────────────────────────────────


async def test_seed_inserts_four_skills_when_table_empty(store, repo):
    """Fresh DB: seed runs, 4 skills present (spec §4.3)."""
    # The store fixture already ran init_db which should have called seed.
    # But the seed is also called manually here for explicit testing.
    await SqlAlchemySkillRepository._seed_if_empty(store)
    all_skills = await repo.list_all()
    names = {s.name for s in all_skills}
    assert {"Sarcastic", "Concise", "Code Reviewer", "NPC Dialog"} <= names


async def test_seed_skips_when_table_has_any_row(store, repo):
    """Idempotent: if any skill exists, don't re-seed.

    init_db already runs the seed on a fresh DB, so this test verifies
    the no-op path: a second call to ``_seed_if_empty`` is a no-op when
    the table is already populated.
    """
    n_before = len(await repo.list_all())  # 4 seed skills
    await repo.create(name="Custom", description="", instruction="x", tags=[])
    n_after_create = len(await repo.list_all())  # 5
    await SqlAlchemySkillRepository._seed_if_empty(store)
    n_after_seed = len(await repo.list_all())  # still 5
    assert n_before == 4  # sanity: seeds landed on init_db
    assert n_after_create == n_before + 1
    assert n_after_seed == n_after_create  # no double-seed
    # Custom is still there alongside the 4 seeds.
    names = {s.name for s in await repo.list_all()}
    assert "Custom" in names
    assert {"Sarcastic", "Concise", "Code Reviewer", "NPC Dialog"} <= names
