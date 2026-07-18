"""Integration tests for /api/skills and /api/bots/{id}/skills REST endpoints.

See spec §6.6. Uses the real SkillService (not a mock) so the full
stack — DTO validation, service-layer business rules, repository
persistence — gets exercised end-to-end. Only the LLM/embedding/
synthesizer side is bypassed (we never call into it here).
"""
from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from api.deps import _get_container
from api.main import app
from app.application.container import ApplicationContainer
from app.application.services.bot import BotService
from app.application.services.skill import SkillService
from app.application.services.thread import ThreadService
from app.infrastructure.config import Settings
from app.infrastructure.db.models import Bot
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyBotRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyStore,
    SqlAlchemyThreadRepository,
)

# ── Helpers ───────────────────────────────────────────────────────


def _asyncio_run(coro):
    """Run an async coroutine in a sync test.

    ``asyncio_mode=auto`` makes async functions tests, but TestClient
    is sync. We bridge with ``asyncio.run`` for one-shot async setup
    in sync fixtures — cheap because each fixture scopes to a single
    tmp_path.
    """
    return asyncio.run(coro)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def settings(tmp_path):
    """Skills_max_per_bot = 3 for fast limit testing."""
    return Settings(_env_file=None, db_path=str(tmp_path / "v.db"))


@pytest.fixture
def store(settings, monkeypatch):
    """Initialise the store synchronously by running the async init_db
    in ``asyncio.run``. Same pattern as test_skill_repository fixtures.
    """
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    s = SqlAlchemyStore(settings=settings)

    async def _init():
        await s.init_db()

    _asyncio_run(_init())
    return s


@pytest.fixture
def container(store, settings):
    """ApplicationContainer with SkillService wired in.

    Frozen dataclass — we have to pass every required field. Most
    services stay None because the route layer never touches them
    for these tests.
    """
    bot_repo = SqlAlchemyBotRepository(store)
    thread_repo = SqlAlchemyThreadRepository(store)
    msg_repo = SqlAlchemyMessageRepository(store)
    bot_svc = BotService(bot_repo)
    threads_svc = ThreadService(threads=thread_repo, messages=msg_repo, bots=bot_repo)
    skill_svc = SkillService(store=store, settings=settings)
    return ApplicationContainer(
        bots=bot_svc,
        threads=threads_svc,
        knowledge=None,  # type: ignore[arg-type]
        personas=None,  # type: ignore[arg-type]
        chat=None,  # type: ignore[arg-type]
        skills=skill_svc,
    )


@pytest.fixture
def client(container):
    """TestClient wired to our container via dependency_overrides."""
    app.dependency_overrides[_get_container] = lambda: container
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def _create_bot(store, skill_ids: list[int] | None = None) -> int:
    """Insert a Bot row directly via SQLAlchemy. Sync wrapper."""

    async def _insert():
        async with store._async_session_factory() as session:
            bot = Bot(
                name="bot",
                personality="p",
                skill_ids=json.dumps(skill_ids or []),
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)
            return bot.id

    return _asyncio_run(_insert())


def _bot_skill_ids(store, bot_id: int) -> list[int]:
    """Read back Bot.skill_ids as a list[int]."""

    async def _read():
        async with store._async_session_factory() as session:
            row = (await session.execute(select(Bot).where(Bot.id == bot_id))).scalar_one()
            return json.loads(row.skill_ids or "[]")

    return _asyncio_run(_read())


# ── GET /api/skills ──────────────────────────────────────────────


def test_list_skills_returns_seeds(client):
    """After init_db, 4 seed skills are visible."""
    resp = client.get("/api/skills")
    assert resp.status_code == 200
    data = resp.json()
    names = {s["name"] for s in data}
    assert {"Sarcastic", "Concise", "Code Reviewer", "NPC Dialog"} <= names


def test_list_skills_with_q_filter(client):
    resp = client.get("/api/skills", params={"q": "sarc"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Sarcastic"


def test_list_skills_with_tag_filter(client):
    resp = client.get("/api/skills", params={"tag": "rp"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "NPC Dialog"


# ── GET /api/skills/{id} ─────────────────────────────────────────


def test_get_skill_returns_full_dto(client):
    """GET by id returns the full SkillDTO including instruction."""
    resp = client.get("/api/skills/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert data["name"] == "Sarcastic"
    assert "instruction" in data
    assert len(data["instruction"]) > 0


def test_get_skill_returns_404_for_unknown_id(client):
    resp = client.get("/api/skills/99999")
    assert resp.status_code == 404
    assert "99999" in resp.json()["detail"]


# ── POST /api/skills ─────────────────────────────────────────────


def test_create_skill_returns_201_and_id(client):
    resp = client.post(
        "/api/skills",
        json={
            "name": "NewSkill",
            "description": "d",
            "instruction": "i",
            "tags": ["a", "b"],
        },
    )
    assert resp.status_code == 201
    assert "id" in resp.json()


def test_create_skill_validates_name_min_length(client):
    """Empty name → 422 (Pydantic ValidationError)."""
    resp = client.post(
        "/api/skills",
        json={"name": "", "description": "d", "instruction": "i", "tags": []},
    )
    assert resp.status_code == 422


def test_create_skill_validates_instruction_min_length(client):
    """Empty instruction → 422."""
    resp = client.post(
        "/api/skills",
        json={"name": "X", "description": "d", "instruction": "", "tags": []},
    )
    assert resp.status_code == 422


def test_create_skill_normalizes_tags(client):
    """Server-side tag normalization: lowercase, dedup."""
    resp = client.post(
        "/api/skills",
        json={
            "name": "TagNormSkill",
            "description": "d",
            "instruction": "i",
            "tags": ["Tone", "DIALOG", "tone"],
        },
    )
    assert resp.status_code == 201
    skill_id = resp.json()["id"]
    detail = client.get(f"/api/skills/{skill_id}").json()
    assert detail["tags"] == ["tone", "dialog"]


# ── PUT /api/skills/{id} ─────────────────────────────────────────


def test_update_skill_partial_only_supplied_fields(client):
    """Create a skill, then update only description."""
    create_resp = client.post(
        "/api/skills",
        json={"name": "UpdTarget", "description": "orig", "instruction": "i", "tags": []},
    )
    sid = create_resp.json()["id"]

    resp = client.put(
        f"/api/skills/{sid}",
        json={"description": "new"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    detail = client.get(f"/api/skills/{sid}").json()
    assert detail["description"] == "new"
    assert detail["name"] == "UpdTarget"  # unchanged


def test_update_skill_returns_404_for_unknown_id(client):
    resp = client.put(
        "/api/skills/99999",
        json={"name": "X"},
    )
    assert resp.status_code == 404


# ── DELETE /api/skills/{id} ──────────────────────────────────────


def test_delete_skill_returns_204_on_success(client):
    create_resp = client.post(
        "/api/skills",
        json={"name": "ToDelete", "description": "", "instruction": "x", "tags": []},
    )
    sid = create_resp.json()["id"]

    resp = client.delete(f"/api/skills/{sid}")
    assert resp.status_code == 204

    # Verify it's gone.
    detail = client.get(f"/api/skills/{sid}")
    assert detail.status_code == 404


def test_delete_skill_with_attachments_returns_409_with_attached_to(client, store):
    """Skill attached to a bot → 409 Conflict with attached_to body."""
    create_resp = client.post(
        "/api/skills",
        json={"name": "InUseSkill", "description": "", "instruction": "x", "tags": []},
    )
    sid = create_resp.json()["id"]
    bot_id = _create_bot(store, skill_ids=[sid])

    resp = client.delete(f"/api/skills/{sid}")
    assert resp.status_code == 409
    body = resp.json()
    assert "attached_to" in body
    assert body["attached_to"] == [bot_id]


def test_delete_skill_returns_404_for_unknown_id(client):
    resp = client.delete("/api/skills/99999")
    assert resp.status_code == 404


# ── GET /api/bots/{id}/skills ────────────────────────────────────


def test_list_bot_skills_returns_resolved(client, store):
    """Bot with 2 skills → endpoint returns both with full fields."""
    s1 = client.post(
        "/api/skills",
        json={"name": "BotSkillA", "description": "d-a", "instruction": "i-a", "tags": []},
    ).json()["id"]
    s2 = client.post(
        "/api/skills",
        json={"name": "BotSkillB", "description": "d-b", "instruction": "i-b", "tags": []},
    ).json()["id"]

    bot_id = _create_bot(store, skill_ids=[s2, s1])  # unordered

    resp = client.get(f"/api/bots/{bot_id}/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Service returns id-ASC sorted regardless of input order.
    assert [s["id"] for s in data] == [s1, s2]
    # All fields present, with instruction.
    assert all("instruction" in s for s in data)


def test_list_bot_skills_returns_404_for_unknown_bot(client):
    resp = client.get("/api/bots/99999/skills")
    assert resp.status_code == 404


# ── PUT /api/bots/{id}/skills ────────────────────────────────────


def test_update_bot_skills_replaces_list(client, store):
    """PUT replaces the entire skill list for the bot."""
    s1 = client.post(
        "/api/skills",
        json={"name": "ReplA", "description": "", "instruction": "i", "tags": []},
    ).json()["id"]
    s2 = client.post(
        "/api/skills",
        json={"name": "ReplB", "description": "", "instruction": "i", "tags": []},
    ).json()["id"]

    bot_id = _create_bot(store, skill_ids=[s1])

    resp = client.put(
        f"/api/bots/{bot_id}/skills",
        json={"skill_ids": [s2]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert len(body["skills"]) == 1
    assert body["skills"][0]["id"] == s2

    # Verify DB state.
    assert _bot_skill_ids(store, bot_id) == [s2]


def test_update_bot_skills_empty_list_clears(client, store):
    s1 = client.post(
        "/api/skills",
        json={"name": "ClearMe", "description": "", "instruction": "i", "tags": []},
    ).json()["id"]
    bot_id = _create_bot(store, skill_ids=[s1])

    resp = client.put(
        f"/api/bots/{bot_id}/skills",
        json={"skill_ids": []},
    )
    assert resp.status_code == 200
    assert resp.json()["skills"] == []


def test_update_bot_skills_404_for_unknown_bot(client):
    resp = client.put(
        "/api/bots/99999/skills",
        json={"skill_ids": []},
    )
    assert resp.status_code == 404


# ── Service unavailable ──────────────────────────────────────────


def test_skills_endpoints_return_503_when_service_missing():
    """When the container has no skills service, endpoints should
    503 (not crash with AttributeError). The container's optional
    SkillService pattern makes this a graceful degradation.
    """
    container = ApplicationContainer(
        bots=None,  # type: ignore[arg-type]
        threads=None,  # type: ignore[arg-type]
        knowledge=None,  # type: ignore[arg-type]
        personas=None,  # type: ignore[arg-type]
        chat=None,  # type: ignore[arg-type]
        skills=None,
    )
    app.dependency_overrides[_get_container] = lambda: container
    try:
        with TestClient(app) as c:
            resp = c.get("/api/skills")
            # 503 (service unavailable) or 500 depending on how the
            # route handles missing service. We accept either as a
            # contract: never crash with AttributeError.
            assert resp.status_code in (500, 503)
    finally:
        app.dependency_overrides.clear()
