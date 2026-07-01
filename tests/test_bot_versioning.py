"""Tests for bot versioning (snapshots, list, restore).

Two layers:

* Integration tests against a real ``SqlAlchemyStore`` running
  Alembic migrations on a temp SQLite file — exercise the full repo
  path, cascade delete, JSON roundtrip and snapshot equality.
* Service-level tests with a fake ``BotVersionRepository`` covering
  ``BotService.update_bot`` auto-snapshot behaviour, restore-before-
  save semantics, and "no version created on no-op save".
"""

from __future__ import annotations

import json
import os
import sys

# Stub external libs that the application pulls in via conftest.py.
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("langgraph", MagicMock())
sys.modules.setdefault("langgraph.graph", MagicMock())
sys.modules.setdefault("langchain_openai", MagicMock())
sys.modules.setdefault("langchain_core", MagicMock())
sys.modules.setdefault("langchain_core.messages", MagicMock())
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_chroma", MagicMock())

from app.application.dto import UpdateBotCommand  # noqa: E402
from app.application.exceptions import NotFoundError  # noqa: E402
from app.application.services.bot import BotService  # noqa: E402
from app.application.services.bot_version import (  # noqa: E402
    BotVersionService,
    serialize_bot,
)
from app.infrastructure.config import Settings  # noqa: E402
from app.infrastructure.db.models import Bot, BotVersion  # noqa: E402
from app.infrastructure.repositories.sqlalchemy import (  # noqa: E402
    SqlAlchemyBotRepository,
    SqlAlchemyBotVersionRepository,
    SqlAlchemyStore,
)

# ── helpers ──────────────────────────────────────────────────────────


async def _seed_bot(store: SqlAlchemyStore) -> int:
    repo = SqlAlchemyBotRepository(store)
    return await repo.create(
        name="Luna",
        personality="mystic",
        first_message="hi",
        scenario="garden",
        description="",
        categories=["Fantasy"],
        alternate_greetings=["a", "b"],
        mes_example="<START>",
    )


@pytest.fixture
async def store(tmp_path, monkeypatch):
    """Build a SqlAlchemyStore backed by a temp SQLite file.

    Patches ``Settings.from_env`` so Alembic (which calls it directly
    in ``alembic/env.py`` to read ``db_url_for_alembic``) migrates the
    SAME temp file the store uses — otherwise Alembic would migrate
    the project's real DB and leave the temp file empty.
    """
    settings = Settings(_env_file=None, db_path=str(tmp_path / "v.db"))

    # Alembic's env.py calls ``Settings.from_env()`` directly. Patch it
    # so it returns our test settings (which point at the temp file).
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))

    s = SqlAlchemyStore(settings=settings)
    await s.init_db()
    yield s
    # Clean up the underlying file — tmp_path cleanup happens after.
    if os.path.exists(settings.db_path):
        try:
            os.remove(settings.db_path)
        except OSError:
            pass


@pytest.fixture
async def bot_id(store):
    return await _seed_bot(store)


# ── serialize_bot shape ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_serialize_bot_roundtrip(store, bot_id):
    repo = SqlAlchemyBotRepository(store)
    bot = await repo.get(bot_id)
    assert bot is not None
    snap = json.loads(serialize_bot(bot))

    assert snap["name"] == "Luna"
    assert snap["personality"] == "mystic"
    assert snap["first_message"] == "hi"
    assert snap["scenario"] == "garden"
    assert snap["categories"] == ["Fantasy"]
    assert snap["alternate_greetings"] == ["a", "b"]
    assert snap["mes_example"] == "<START>"
    assert snap["bot_type"] == "rp"
    assert snap["avatar_path"] is None
    # No leaking of internal fields
    assert "id" not in snap
    assert "threads" not in snap


# ── Repository: list / get / get_max / delete / add ───────────────────


@pytest.mark.asyncio
async def test_repo_add_increments_and_returns_id(store, bot_id):
    repo = SqlAlchemyBotVersionRepository(store)
    v1 = BotVersion(
        bot_id=bot_id,
        version_number=1,
        snapshot_json=json.dumps({"name": "Luna"}),
        note="",
        source="manual",
    )
    v1_id = await repo.add(v1)
    assert v1_id > 0

    v2 = BotVersion(
        bot_id=bot_id,
        version_number=2,
        snapshot_json=json.dumps({"name": "Luna2"}),
        note="",
        source="auto",
    )
    await repo.add(v2)

    rows = await repo.list_by_bot(bot_id)
    assert [r.version_number for r in rows] == [2, 1]  # DESC


@pytest.mark.asyncio
async def test_repo_get_max_returns_zero_when_empty(store, bot_id):
    repo = SqlAlchemyBotVersionRepository(store)
    assert await repo.get_max_version(bot_id) == 0


@pytest.mark.asyncio
async def test_repo_delete(store, bot_id):
    repo = SqlAlchemyBotVersionRepository(store)
    v = BotVersion(
        bot_id=bot_id,
        version_number=1,
        snapshot_json="{}",
        note="",
        source="manual",
    )
    vid = await repo.add(v)
    await repo.delete(vid)
    assert await repo.get(vid) is None


@pytest.mark.asyncio
async def test_cascade_delete_with_bot(store, bot_id):
    """Deleting the bot must remove its versions (FK ON DELETE CASCADE)."""
    bv_repo = SqlAlchemyBotVersionRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    await bv_repo.add(
        BotVersion(
            bot_id=bot_id,
            version_number=1,
            snapshot_json="{}",
            note="",
            source="manual",
        )
    )
    assert len(await bv_repo.list_by_bot(bot_id)) == 1
    await bot_repo.delete(bot_id)
    assert await bv_repo.list_by_bot(bot_id) == []


# ── BotVersionService: create_version / restore / list ───────────────


@pytest.mark.asyncio
async def test_service_create_version_assigns_monotonic_numbers(store, bot_id):
    version_repo = SqlAlchemyBotVersionRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    svc = BotVersionService(version_repo, bot_repo)

    v1 = await svc.create_version(bot_id, note="first", source="manual")
    v2 = await svc.create_version(bot_id, note="second", source="manual")
    assert v1.version_number == 1
    assert v2.version_number == 2

    snap = json.loads(v1.snapshot_json)
    assert snap["name"] == "Luna"


@pytest.mark.asyncio
async def test_service_create_version_unknown_bot_raises(store):
    version_repo = SqlAlchemyBotVersionRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    svc = BotVersionService(version_repo, bot_repo)

    with pytest.raises(NotFoundError):
        await svc.create_version(99999, note="nope")


@pytest.mark.asyncio
async def test_service_list_versions_unknown_bot_raises(store):
    version_repo = SqlAlchemyBotVersionRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    svc = BotVersionService(version_repo, bot_repo)
    with pytest.raises(NotFoundError):
        await svc.list_versions(99999)


@pytest.mark.asyncio
async def test_service_restore_auto_saves_current_state(store, bot_id):
    """Restore must auto-snapshot the live bot first, then apply."""
    version_repo = SqlAlchemyBotVersionRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    svc = BotVersionService(version_repo, bot_repo)

    # v1 captures "Luna" name
    v1 = await svc.create_version(bot_id, note="initial", source="manual")
    assert v1.id is not None

    # Mutate the bot live
    await bot_repo.update(
        bot_id,
        name="Solaris",
        personality="bright",
        first_message="",
        scenario="",
        description="",
        categories=[],
        bot_type="rp",
        alternate_greetings=[],
        mes_example="",
    )

    # Restore v1
    await svc.restore_version(v1.id)

    # Two versions now: v1 (original Luna), v2 (auto before restore)
    versions = await version_repo.list_by_bot(bot_id)
    assert [v.version_number for v in versions] == [2, 1]

    # The auto version captured "Solaris"
    auto = next(v for v in versions if v.source == "auto")
    auto_snap = json.loads(auto.snapshot_json)
    assert auto_snap["name"] == "Solaris"
    assert "Auto-saved before restore to v1" in auto.note

    # Live bot now back to Luna
    live = await bot_repo.get(bot_id)
    assert live is not None
    assert live.name == "Luna"


@pytest.mark.asyncio
async def test_service_restore_unknown_version_raises(store, bot_id):
    version_repo = SqlAlchemyBotVersionRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    svc = BotVersionService(version_repo, bot_repo)
    with pytest.raises(NotFoundError):
        await svc.restore_version(99999)


@pytest.mark.asyncio
async def test_service_delete_version(store, bot_id):
    version_repo = SqlAlchemyBotVersionRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    svc = BotVersionService(version_repo, bot_repo)

    v = await svc.create_version(bot_id, note="x", source="manual")
    assert v.id is not None
    await svc.delete_version(v.id)
    assert await version_repo.get(v.id) is None


# ── BotService.update_bot auto-snapshot ───────────────────────────────


class _FakeBotVersionRepo:
    """In-memory drop-in for ``SqlAlchemyBotVersionRepository``."""

    def __init__(self):
        self._rows: dict[int, BotVersion] = {}
        self._next_id = 1

    async def add(self, version: BotVersion) -> int:
        vid = self._next_id
        self._next_id += 1
        version.id = vid
        self._rows[vid] = version
        return vid

    async def get_max_version(self, bot_id: int) -> int:
        return max(
            (v.version_number for v in self._rows.values() if v.bot_id == bot_id),
            default=0,
        )


class _FakeBotRepo:
    """Tiny in-memory bot repo sufficient for BotService tests."""

    def __init__(self):
        self._bots: dict[int, Bot] = {}
        self._next_id = 1

    async def get(self, bot_id: int):
        return self._bots.get(bot_id)

    async def list(self):
        return list(self._bots.values())

    async def create(
        self,
        name: str,
        personality: str,
        first_message: str,
        scenario: str = "",
        description: str = "",
        avatar_path: str | None = None,
        categories=None,
        bot_type="rp",
        alternate_greetings=None,
        mes_example: str = "",
    ) -> int:
        bid = self._next_id
        self._next_id += 1
        bot = Bot(
            id=bid,
            name=name,
            personality=personality,
            first_message=first_message,
            scenario=scenario,
            description=description,
            avatar_path=avatar_path,
            categories=json.dumps(categories or []),
            bot_type=bot_type,
            alternate_greetings=json.dumps(alternate_greetings or []),
            mes_example=mes_example,
        )
        self._bots[bid] = bot
        return bid

    async def update(
        self,
        bot_id: int,
        name: str,
        personality: str,
        first_message: str,
        scenario: str = "",
        description: str = "",
        avatar_path: str | None = None,
        categories=None,
        bot_type="rp",
        alternate_greetings=None,
        mes_example: str | None = None,
    ) -> None:
        bot = self._bots[bot_id]
        bot.name = name
        bot.personality = personality
        bot.first_message = first_message
        bot.scenario = scenario
        bot.description = description
        bot.avatar_path = avatar_path
        bot.categories = json.dumps(categories or [])
        bot.bot_type = bot_type
        bot.alternate_greetings = json.dumps(alternate_greetings or [])
        if mes_example is not None:
            bot.mes_example = mes_example

    async def delete(self, bot_id: int) -> None:
        self._bots.pop(bot_id, None)

    async def get_with_thread_counts(self):
        return [(b, 0) for b in self._bots.values()]


@pytest.mark.asyncio
async def test_bot_service_update_creates_auto_version_on_change():
    bots = _FakeBotRepo()
    versions = _FakeBotVersionRepo()
    svc = BotService(bots, bot_versions=versions)

    bid = await bots.create(
        name="Luna",
        personality="mystic",
        first_message="hi",
        scenario="garden",
        description="",
        categories=["Fantasy"],
        alternate_greetings=[],
        mes_example="",
    )

    # Real change → auto-version #1
    await svc.update_bot(
        UpdateBotCommand(
            bot_id=bid,
            name="Luna2",
            personality="mystic",
            first_message="hi",
            scenario="garden",
            description="",
            categories=["Fantasy"],
            bot_type="rp",
            alternate_greetings=[],
            mes_example="",
        )
    )
    rows = list(versions._rows.values())
    assert len(rows) == 1
    assert rows[0].source == "auto"
    assert rows[0].note == ""
    assert rows[0].version_number == 1


@pytest.mark.asyncio
async def test_bot_service_update_noop_creates_no_version():
    bots = _FakeBotRepo()
    versions = _FakeBotVersionRepo()
    svc = BotService(bots, bot_versions=versions)

    bid = await bots.create(
        name="Luna",
        personality="mystic",
        first_message="hi",
        scenario="garden",
        description="",
        categories=["Fantasy"],
        alternate_greetings=[],
        mes_example="",
    )

    # Same data → no version
    await svc.update_bot(
        UpdateBotCommand(
            bot_id=bid,
            name="Luna",
            personality="mystic",
            first_message="hi",
            scenario="garden",
            description="",
            categories=["Fantasy"],
            bot_type="rp",
            alternate_greetings=[],
            mes_example="",
        )
    )
    assert list(versions._rows.values()) == []


@pytest.mark.asyncio
async def test_bot_service_update_without_version_repo_is_safe():
    """BotService must work when bot_versions is None (legacy callers)."""
    bots = _FakeBotRepo()
    svc = BotService(bots)  # no bot_versions
    bid = await bots.create(
        name="Luna",
        personality="m",
        first_message="",
        scenario="",
        description="",
        categories=[],
        alternate_greetings=[],
        mes_example="",
    )
    await svc.update_bot(
        UpdateBotCommand(
            bot_id=bid,
            name="X",
            personality="m",
            first_message="",
            scenario="",
            description="",
            categories=[],
            bot_type="rp",
            alternate_greetings=[],
            mes_example="",
        )
    )
    assert (await bots.get(bid)).name == "X"


@pytest.mark.asyncio
async def test_bot_service_update_unknown_bot_raises():
    bots = _FakeBotRepo()
    svc = BotService(bots)
    with pytest.raises(NotFoundError):
        await svc.update_bot(
            UpdateBotCommand(
                bot_id=99999,
                name="x",
                personality="x",
                first_message="",
                scenario="",
                description="",
                categories=[],
                bot_type="rp",
                alternate_greetings=[],
                mes_example="",
            )
        )


# ── API smoke (real container, real DB) ──────────────────────────────


@pytest.mark.asyncio
async def test_api_versions_endpoints_roundtrip(store, bot_id):
    """Spin the FastAPI app against a freshly seeded bot and exercise
    list / create / get / restore / delete via httpx.AsyncClient.
    """
    # Build a real container backed by the same store.
    from app.application.container import ApplicationContainer
    from app.application.services.bot import BotService
    from app.application.services.bot_version import BotVersionService
    from app.infrastructure.repositories.sqlalchemy import (
        SqlAlchemyBotRepository,
        SqlAlchemyBotVersionRepository,
    )

    bot_repo = SqlAlchemyBotRepository(store)
    version_repo = SqlAlchemyBotVersionRepository(store)
    container = ApplicationContainer(
        bots=BotService(bot_repo, bot_versions=version_repo),
        threads=None,
        knowledge=None,
        personas=None,
        bot_versions=BotVersionService(version_repo, bot_repo),
    )

    # Override the app's container resolver for this test only.
    from fastapi.testclient import TestClient

    from api.deps import _get_container
    from api.main import app

    app.dependency_overrides[_get_container] = lambda: container
    try:
        with TestClient(app) as client:
            # Mutate the bot so the auto-snapshot hook has something to do.
            r = client.put(
                f"/api/bots/{bot_id}",
                json={
                    "name": "Solaris",
                    "personality": "bright",
                    "first_message": "",
                    "scenario": "",
                    "description": "",
                    "categories": [],
                    "bot_type": "rp",
                    "alternate_greetings": [],
                    "mes_example": "",
                },
            )
            assert r.status_code == 200, r.text

            # List — should now have 1 auto version
            r = client.get(f"/api/bots/{bot_id}/versions")
            assert r.status_code == 200
            versions = r.json()
            assert len(versions) == 1
            assert versions[0]["source"] == "auto"
            assert versions[0]["snapshot"] is None  # list endpoint strips snapshot
            version_id = versions[0]["id"]

            # Manual snapshot with a note
            r = client.post(
                f"/api/bots/{bot_id}/versions",
                json={"note": "after tone change"},
            )
            assert r.status_code == 201
            manual = r.json()
            assert manual["source"] == "manual"
            assert manual["note"] == "after tone change"
            assert manual["snapshot"] is not None
            assert manual["snapshot"]["name"] == "Solaris"
            manual_id = manual["id"]

            # Restore the auto version → live bot goes back to Luna,
            # AND a new auto version captures the current "Solaris"
            # state first.
            r = client.post(f"/api/bots/{bot_id}/versions/{version_id}/restore")
            assert r.status_code == 200, r.text
            assert r.json()["restored_from"] == 1

            r = client.get(f"/api/bots/{bot_id}")
            assert r.status_code == 200
            assert r.json()["name"] == "Luna"

            # Now 3 versions: manual (#2), auto-snapshot-before-restore (#3),
            # original auto (#1)
            r = client.get(f"/api/bots/{bot_id}/versions")
            versions = r.json()
            assert len(versions) == 3
            nums = sorted(v["version_number"] for v in versions)
            assert nums == [1, 2, 3]

            # Delete the manual version
            r = client.delete(f"/api/bots/{bot_id}/versions/{manual_id}")
            assert r.status_code == 200

            r = client.get(f"/api/bots/{bot_id}/versions")
            assert len(r.json()) == 2

            # Wrong bot_id in path → 404
            r = client.get(f"/api/bots/{99999}/versions/{version_id}")
            assert r.status_code == 404
    finally:
        app.dependency_overrides.pop(_get_container, None)
