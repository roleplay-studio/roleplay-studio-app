"""Integration tests for ``SqlAlchemySettingsRepository``.

Boots a real ``SqlAlchemyStore`` on a temp SQLite file (so alembic
runs end-to-end), then exercises the singleton ``app_settings`` row
and verifies bot-side orphan-stripping via ``SettingsService``.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.application.services.settings import SettingsService
from app.infrastructure.config import Settings
from app.infrastructure.db.models import AppSettings
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyBotRepository,
    SqlAlchemySettingsRepository,
    SqlAlchemyStore,
)

# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture
async def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Build a SqlAlchemyStore backed by a temp SQLite file.

    Same trick as ``test_bot_versioning``: patch
    ``Settings.from_env`` so alembic (which calls it directly in
    ``alembic/env.py``) migrates the SAME temp file.
    """
    db_path = str(tmp_path / "settings.db")
    settings = Settings(_env_file=None, db_path=db_path)
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))

    s = SqlAlchemyStore(settings=settings)
    await s.init_db()
    try:
        yield s, db_path
    finally:
        if os.path.exists(db_path):
            try:
                os.remove(db_path)
            except OSError:
                pass


# ── SqlAlchemySettingsRepository ────────────────────────────────────


@pytest.mark.asyncio
async def test_repo_get_returns_none_when_unseeded(store):
    s, _db = store
    repo = SqlAlchemySettingsRepository(s)
    assert await repo.get_bot_categories() is None


@pytest.mark.asyncio
async def test_repo_persists_via_insert_then_read(store):
    s, _db = store
    repo = SqlAlchemySettingsRepository(s)
    await repo.set_bot_categories(
        ["Anime", "Game"], '["Anime", "Game"]'
    )
    assert await repo.get_bot_categories() == ["Anime", "Game"]


@pytest.mark.asyncio
async def test_repo_upserts_when_called_twice(store):
    """Two ``set_bot_categories`` calls shouldn't create two rows.

    The first INSERT writes id=1; the second hits the IntegrityError
    path and falls back to UPDATE. After both calls we should still
    have a single row carrying the latest value.
    """
    s, db = store
    repo = SqlAlchemySettingsRepository(s)
    await repo.set_bot_categories(["Anime"], '["Anime"]')
    await repo.set_bot_categories(
        ["Anime", "Game"], '["Anime", "Game"]'
    )
    out = await repo.get_bot_categories()
    assert out == ["Anime", "Game"]

    # Direct DB check: still exactly one row.
    import aiosqlite

    async with aiosqlite.connect(db) as conn:
        cur = await conn.execute("SELECT COUNT(*) FROM app_settings")
        (count,) = await cur.fetchone()
        assert count == 1, "app_settings must remain a singleton"


@pytest.mark.asyncio
async def test_singleton_constraint_rejects_id_2(store):
    """The CHECK constraint must reject any second row with id != 1."""
    s, _db = store
    # Pre-seed: one row.
    await SqlAlchemySettingsRepository(s).set_bot_categories(
        ["Anime"], '["Anime"]'
    )
    # Bypass the repo to insert a second row — DB must refuse it.
    async with s._async_session_factory() as session:
        session.add(AppSettings(id=2, bot_categories_json='[""]'))
        with pytest.raises(Exception):
            await session.commit()


# ── SettingsService end-to-end ──────────────────────────────────────


@pytest.mark.asyncio
async def test_service_seeds_default_categories_on_first_read(store):
    s, _db = store
    svc = SettingsService(SqlAlchemySettingsRepository(s))
    out = await svc.list_bot_categories()
    # Defaults from DEFAULT_BOT_CATEGORIES — Anime/Game/etc.
    assert "Anime" in out
    assert "Game" in out
    assert await svc.list_bot_categories() == out  # stable on reread


@pytest.mark.asyncio
async def test_full_lifecycle(store):
    s, _db = store
    svc = SettingsService(SqlAlchemySettingsRepository(s))
    await svc.replace_all(["Alpha", "Beta"])
    assert await svc.list_bot_categories() == ["Alpha", "Beta"]

    assert await svc.add_category("Gamma") == ["Alpha", "Beta", "Gamma"]
    assert await svc.rename_category("Beta", "BetaPrime") == [
        "Alpha",
        "BetaPrime",
        "Gamma",
    ]
    assert await svc.delete_category("Alpha") == ["BetaPrime", "Gamma"]


# ── Bot orphan-stripping ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bot_persists_categories_as_legacy_string(store):
    """A bot with a now-deleted category keeps the JSON string, so
    the user can audit / clean it up via the dashboard rather than
    losing data behind the scenes."""
    s, _db = store
    settings_svc = SettingsService(SqlAlchemySettingsRepository(s))
    bot_repo = SqlAlchemyBotRepository(s)

    # Start from a clean, controlled slate so the test doesn't
    # depend on the DEFAULT_BOT_CATEGORIES seed.
    await settings_svc.replace_all(
        ["SoonRemoved", "Survivor"]
    )

    # Persist a bot carrying both names.
    bot_id = await bot_repo.create(
        name="Luna",
        personality="mystic",
        first_message="hi",
        categories=["SoonRemoved", "Survivor"],
    )

    # Remove the category via the settings service.
    await settings_svc.delete_category("SoonRemoved")

    # ``Bot.categories`` still contains the orphan JSON. The frontend
    # filters it via ``filter_valid`` / surfaces it via
    # ``categories_invalid``.
    import json

    bot = await bot_repo.get(bot_id)
    assert bot is not None
    assert json.loads(bot.categories) == ["SoonRemoved", "Survivor"]


@pytest.mark.asyncio
async def test_bot_categories_invalid_surface_in_response(store):
    """BotResponse carries ``categories_invalid`` whenever the bot
    references a category the user has since removed."""
    from app.application.dto import BotResponse

    s, _db = store
    settings_svc = SettingsService(SqlAlchemySettingsRepository(s))
    bot_repo = SqlAlchemyBotRepository(s)
    await settings_svc.replace_all(["Survivor"])

    bot_id = await bot_repo.create(
        name="Orphan",
        personality="ghost",
        first_message="boo",
        categories=["SoonRemoved", "Survivor"],
    )
    bot = await bot_repo.get(bot_id)
    assert bot is not None

    valid = set(await settings_svc.list_bot_categories())
    response = BotResponse.from_orm_bot(
        bot, thread_count=0, valid_categories=valid
    )
    assert response.categories == ["SoonRemoved", "Survivor"]
    assert response.categories_invalid == ["SoonRemoved"]


@pytest.mark.asyncio
async def test_filter_valid_drops_orphan(store):
    s, _db = store
    settings_svc = SettingsService(SqlAlchemySettingsRepository(s))
    await settings_svc.replace_all(["Survivor"])
    out = await settings_svc.filter_valid(
        ["SoonRemoved", "Survivor", "Survivor"]
    )
    assert out == ["Survivor"]


@pytest.mark.asyncio
async def test_categories_invalid_for_returns_orphan(store):
    s, _db = store
    settings_svc = SettingsService(SqlAlchemySettingsRepository(s))
    await settings_svc.replace_all(["Survivor"])
    invalid = await settings_svc.categories_invalid_for(
        ["SoonRemoved", "Survivor", "Ghost"]
    )
    assert sorted(invalid) == ["Ghost", "SoonRemoved"]
