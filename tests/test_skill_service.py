"""Tests for SkillService — service layer with validation + business rules.

See spec §6.2.
"""
import json

import pytest

from app.application.dto import (
    CreateSkillCommand,
    SkillDTO,
    UpdateSkillCommand,
)
from app.application.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.application.services.skill import SkillService
from app.infrastructure.config import Settings
from app.infrastructure.db.models import Bot
from app.infrastructure.repositories.sqlalchemy import SqlAlchemyStore

# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def settings():
    """Low max-skills-per-bot for fast limit testing (3 instead of 10)."""
    return Settings(_env_file=None, skills_max_per_bot=3)


@pytest.fixture
async def store(tmp_path, monkeypatch):
    """Same pattern as tests/test_skill_repository.py — force alembic
    and SqlAlchemyStore to use the same Settings so migrations apply to
    the test's tmp_path SQLite, not the project-default conversations.db.
    """
    s = Settings(_env_file=None, db_path=str(tmp_path / "v.db"))
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: s))
    store = SqlAlchemyStore(settings=s)
    await store.init_db()
    yield store


@pytest.fixture
def service(store, settings):
    return SkillService(store=store, settings=settings)


# ── list_skills / get_skill ───────────────────────────────────────


async def test_list_skills_empty_returns_empty_list(service):
    # After init_db, 4 seeds already exist — empty list is not realistic,
    # so check that listing returns 4 seeds + nothing extra.
    skills = await service.list_skills()
    assert len(skills) == 4  # the 4 seed skills
    assert all(isinstance(s, SkillDTO) for s in skills)


async def test_list_skills_with_q_filter(service):
    """q filter narrows the result (case-insensitive substring)."""
    results = await service.list_skills(q="sarc")
    assert len(results) == 1
    assert results[0].name == "Sarcastic"


async def test_list_skills_with_tag_filter(service):
    """tag filter is exact-match on a single tag (case-insensitive)."""
    results = await service.list_skills(tag="code")
    assert len(results) == 1
    assert results[0].name == "Code Reviewer"


async def test_get_skill_returns_dto(service):
    """get_skill returns full SkillDTO (with instruction)."""
    skill = await service.get_skill(1)
    assert isinstance(skill, SkillDTO)
    assert skill.id == 1
    assert skill.instruction  # non-empty


async def test_get_skill_raises_not_found(service):
    with pytest.raises(NotFoundError, match="999"):
        await service.get_skill(999)


# ── create_skill ──────────────────────────────────────────────────


async def test_create_skill_returns_id(service):
    sid = await service.create_skill(
        CreateSkillCommand(
            name="MySkill", description="d", instruction="i", tags=["t"]
        )
    )
    assert isinstance(sid, int)


async def test_create_skill_rejects_duplicate_name(service):
    """Duplicate name → ValidationError with 409 hint (mapped to ConflictError)."""
    await service.create_skill(
        CreateSkillCommand(name="DupSkill", description="", instruction="x", tags=[])
    )
    with pytest.raises(ValidationError, match="already exists"):
        await service.create_skill(
            CreateSkillCommand(name="DupSkill", description="", instruction="y", tags=[])
        )


async def test_create_skill_persists_via_repo(service):
    """Service delegates to repo — verify via direct repo lookup."""
    sid = await service.create_skill(
        CreateSkillCommand(
            name="PersistenceSkill", description="d", instruction="i", tags=["a", "b"]
        )
    )
    skill = await service.get_skill(sid)
    assert skill.name == "PersistenceSkill"
    assert skill.tags == ["a", "b"]


# ── update_skill ──────────────────────────────────────────────────


async def test_update_skill_partial_only_touches_supplied_fields(service):
    """update with only description leaves name + tags unchanged."""
    sid = await service.create_skill(
        CreateSkillCommand(
            name="UpdSkill", description="orig", instruction="x", tags=["t1"]
        )
    )
    await service.update_skill(sid, UpdateSkillCommand(description="new"))
    skill = await service.get_skill(sid)
    assert skill.description == "new"
    assert skill.name == "UpdSkill"  # unchanged
    assert skill.tags == ["t1"]  # unchanged


async def test_update_skill_rejects_duplicate_name_collision(service):
    """If update changes name to one that exists, raise ValidationError."""
    await service.create_skill(
        CreateSkillCommand(name="First", description="", instruction="x", tags=[])
    )
    sid2 = await service.create_skill(
        CreateSkillCommand(name="Second", description="", instruction="y", tags=[])
    )
    with pytest.raises(ValidationError, match="already exists"):
        await service.update_skill(sid2, UpdateSkillCommand(name="First"))


async def test_update_skill_to_same_name_works(service):
    """No-op rename (same name) should not trigger duplicate check."""
    sid = await service.create_skill(
        CreateSkillCommand(name="SameName", description="", instruction="x", tags=[])
    )
    # Setting name to itself should be fine.
    await service.update_skill(sid, UpdateSkillCommand(name="SameName"))
    skill = await service.get_skill(sid)
    assert skill.name == "SameName"


async def test_update_skill_unknown_id_raises_not_found(service):
    with pytest.raises(NotFoundError, match="999"):
        await service.update_skill(999, UpdateSkillCommand(name="X"))


# ── delete_skill ──────────────────────────────────────────────────


async def test_delete_skill_no_attachments_succeeds(service):
    sid = await service.create_skill(
        CreateSkillCommand(name="Deletable", description="", instruction="x", tags=[])
    )
    await service.delete_skill(sid)  # no exception
    with pytest.raises(NotFoundError):
        await service.get_skill(sid)


async def test_delete_skill_with_attachments_raises_conflict(service, store):
    """When bots reference this skill, raise ConflictError with attached_to."""
    sid = await service.create_skill(
        CreateSkillCommand(name="InUse", description="", instruction="x", tags=[])
    )
    # Attach via direct DB write (service.update_bot_skills tests come later)
    async with store._async_session_factory() as session:
        bot1 = Bot(name="b1", personality="p", skill_ids=json.dumps([sid]))
        bot2 = Bot(name="b2", personality="p", skill_ids=json.dumps([sid]))
        session.add_all([bot1, bot2])
        await session.commit()
        bot1_id, bot2_id = bot1.id, bot2.id

    with pytest.raises(ConflictError) as exc_info:
        await service.delete_skill(sid)
    assert exc_info.value.http_status == 409
    assert sorted(exc_info.value.attached_to) == sorted([bot1_id, bot2_id])


async def test_delete_skill_unknown_id_raises_not_found(service):
    """delete on a non-existent id raises NotFoundError (not ConflictError)."""
    with pytest.raises(NotFoundError, match="999"):
        await service.delete_skill(999)


# ── update_bot_skills ─────────────────────────────────────────────


async def test_update_bot_skills_replaces_list_and_dedupes(service, store):
    """Replace bot's skill list; dedup input."""
    sid1 = await service.create_skill(
        CreateSkillCommand(name="BotSkill1", description="", instruction="x", tags=[])
    )
    sid2 = await service.create_skill(
        CreateSkillCommand(name="BotSkill2", description="", instruction="y", tags=[])
    )
    async with store._async_session_factory() as session:
        bot = Bot(name="b", personality="p", skill_ids="[]")
        session.add(bot)
        await session.commit()
        bot_id = bot.id

    # Replace with duplicates; result should be deduped.
    result = await service.update_bot_skills(
        bot_id=bot_id,
        skill_ids=[sid1, sid2, sid1, sid1],  # 4 input, 2 unique
    )
    assert len(result) == 2
    assert {s.id for s in result} == {sid1, sid2}

    # Verify DB state.
    async with store._async_session_factory() as session:
        from sqlalchemy import select

        bot_row = (await session.execute(select(Bot).where(Bot.id == bot_id))).scalar_one()
        assert json.loads(bot_row.skill_ids) == sorted([sid1, sid2])  # order-preserving


async def test_update_bot_skills_enforces_max_limit(service, store):
    """Settings.skills_max_per_bot = 3 → 4+ raises ValidationError."""
    async with store._async_session_factory() as session:
        bot = Bot(name="b", personality="p", skill_ids="[]")
        session.add(bot)
        await session.commit()
        bot_id = bot.id

    with pytest.raises(ValidationError, match="skills_max_per_bot"):
        await service.update_bot_skills(bot_id=bot_id, skill_ids=[1, 2, 3, 4])


async def test_update_bot_skills_raises_not_found_for_unknown_id(service, store):
    """If any of the requested skill ids doesn't exist, raise NotFoundError."""
    async with store._async_session_factory() as session:
        bot = Bot(name="b", personality="p", skill_ids="[]")
        session.add(bot)
        await session.commit()
        bot_id = bot.id

    with pytest.raises(NotFoundError, match="999"):
        await service.update_bot_skills(bot_id=bot_id, skill_ids=[999])


async def test_update_bot_skills_raises_not_found_for_unknown_bot(service):
    """If bot_id doesn't exist, raise NotFoundError."""
    with pytest.raises(NotFoundError, match="999"):
        await service.update_bot_skills(bot_id=999, skill_ids=[])


async def test_update_bot_skills_empty_list_clears_existing(service, store):
    """Empty input clears the bot's skills."""
    sid = await service.create_skill(
        CreateSkillCommand(name="ClearMe", description="", instruction="x", tags=[])
    )
    async with store._async_session_factory() as session:
        bot = Bot(name="b", personality="p", skill_ids=json.dumps([sid]))
        session.add(bot)
        await session.commit()
        bot_id = bot.id

    result = await service.update_bot_skills(bot_id=bot_id, skill_ids=[])
    assert result == []

    async with store._async_session_factory() as session:
        from sqlalchemy import select

        bot_row = (await session.execute(select(Bot).where(Bot.id == bot_id))).scalar_one()
        assert json.loads(bot_row.skill_ids) == []


# ── list_for_bot_with_ids ─────────────────────────────────────────


async def test_list_for_bot_with_ids_returns_resolved(service):
    """list_for_bot_with_ids is the bulk-resolver ChatService uses."""
    sid1 = await service.create_skill(
        CreateSkillCommand(name="ResolveA", description="d-a", instruction="i-a", tags=[])
    )
    sid2 = await service.create_skill(
        CreateSkillCommand(name="ResolveB", description="d-b", instruction="i-b", tags=[])
    )
    result = await service.list_for_bot_with_ids([sid2, sid1])
    assert [s.id for s in result] == [sid1, sid2]  # sorted by id ASC (per spec §6.1)
    assert all(isinstance(s, SkillDTO) for s in result)


async def test_list_for_bot_with_ids_silently_skips_unknown(service):
    """Orphan ids don't raise — defensive for legacy/orphan rows."""
    sid = await service.create_skill(
        CreateSkillCommand(name="KeepMe", description="", instruction="x", tags=[])
    )
    result = await service.list_for_bot_with_ids([sid, 99999])
    assert len(result) == 1
    assert result[0].id == sid


async def test_list_for_bot_with_ids_empty_returns_empty(service):
    assert await service.list_for_bot_with_ids([]) == []
