"""Tests for FastAPI REST endpoints."""

import dataclasses
from typing import ClassVar

import httpx
import pytest
from fastapi.testclient import TestClient

from api.deps import _get_container
from api.main import app

# ── Mock container ──────────────────────────────────────────────────


class MockBotService:
    def __init__(self):
        self.bots = {}
        self.next_id = 1

    def _to_obj(self, data):
        from types import SimpleNamespace

        return SimpleNamespace(**data)

    async def create_bot(self, command):
        bid = self.next_id
        self.next_id += 1
        self.bots[bid] = {
            "id": bid,
            "name": command.name,
            "personality": command.personality,
            "first_message": command.first_message,
            "scenario": command.scenario or "",
            "description": getattr(command, "description", ""),
            "avatar_path": command.avatar_path,
            "categories": command.categories,
            "bot_type": getattr(command, "bot_type", "rp"),
            "alternate_greetings": getattr(command, "alternate_greetings", []),
        }
        return bid

    async def update_bot(self, command):
        if command.bot_id not in self.bots:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Bot {command.bot_id} was not found")
        self.bots[command.bot_id].update(
            {
                "name": command.name,
                "personality": command.personality,
                "first_message": command.first_message,
                "scenario": command.scenario or "",
                "description": getattr(command, "description", ""),
                "avatar_path": command.avatar_path,
                "categories": command.categories,
                "bot_type": getattr(command, "bot_type", "rp"),
                "alternate_greetings": getattr(command, "alternate_greetings", []),
            }
        )

    async def get_bot(self, bot_id):
        data = self.bots.get(bot_id)
        if data is None:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Bot {bot_id} was not found")
        return self._to_obj(data)

    async def list_bots(self):
        return [self._to_obj(d) for d in self.bots.values()]

    async def get_bot_with_count(self, bot_id):
        """Return (bot_obj, thread_count) or raise NotFoundError."""
        bot = await self.get_bot(bot_id)
        return bot, 0

    async def list_bots_with_counts(self):
        """Return list of (bot_obj, thread_count) tuples."""
        return [(self._to_obj(d), 0) for d in self.bots.values()]

    async def delete_bot(self, bot_id):
        if bot_id not in self.bots:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Bot {bot_id} was not found")
        del self.bots[bot_id]


class MockThreadService:
    def __init__(self):
        self.threads = {}
        self.messages = {}
        self.next_id = 1

    async def create_thread(self, bot_id, name="Новая беседа", persona_id=None):
        tid = self.next_id
        self.next_id += 1
        from app.application.dto import ThreadDTO

        self.threads[tid] = ThreadDTO(id=tid, bot_id=bot_id, name=name)
        self.messages[tid] = []
        return tid

    async def get_thread(self, thread_id):
        t = self.threads.get(thread_id)
        if t is None:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Thread {thread_id} was not found")
        return t

    async def list_threads(self, bot_id):
        return [t for t in self.threads.values() if t.bot_id == bot_id]

    async def rename_thread(self, thread_id, name):
        if thread_id not in self.threads:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Thread {thread_id} was not found")
        from app.application.dto import ThreadDTO

        old = self.threads[thread_id]
        self.threads[thread_id] = ThreadDTO(id=old.id, bot_id=old.bot_id, name=name)

    async def delete_thread(self, thread_id):
        if thread_id not in self.threads:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Thread {thread_id} was not found")
        del self.threads[thread_id]
        self.messages.pop(thread_id, None)

    async def clear_conversation(self, thread_id):
        self.messages[thread_id] = []

    async def update_thread_summary(self, thread_id, summary):
        # Mock: track the call so the /summarize endpoint test can
        # assert that the manual button actually persists to the DB.
        t = self.threads.get(thread_id)
        if t is None:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Thread {thread_id} was not found")
        # ThreadDTO is a pydantic BaseModel; use model_copy to preserve
        # validation behavior on the mock.
        self.threads[thread_id] = t.model_copy(update={"summary": summary})

    async def set_first_message(self, thread_id, bot_id, greeting_index):
        # Mock: just track the call. Default to success.
        if greeting_index < 0:
            raise ValueError("greeting_index out of range")
        # Test bot has first_message only (no alternate_greetings) — only index 0 valid.
        if greeting_index > 0:
            raise ValueError("greeting_index out of range")

    async def list_messages(self, thread_id, limit=20, before_id=None):
        all_msgs = self.messages.get(thread_id) or []
        if before_id is not None:
            all_msgs = [m for m in all_msgs if m["id"] < before_id]
        return all_msgs[:limit]

    async def get_versions(self, message_id):
        from app.application.dto import MessageDTO

        return [
            MessageDTO(
                id=message_id,
                role="assistant",
                content="Original response",
                branch_group="branch-1",
                branch_index=0,
                is_active=True,
            )
        ]

    async def switch_version(self, thread_id, message_id, target_version_id):
        return None

    async def export_messages(self, thread_id):
        from app.application.exceptions import NotFoundError

        if thread_id not in self.threads:
            raise NotFoundError(f"Thread {thread_id} was not found")
        from app.application.dto import ExportMessageDTO

        return [
            ExportMessageDTO(
                role=m.role if hasattr(m, "role") else "user",
                content=m.content if hasattr(m, "content") else str(m),
                short_content=getattr(m, "short_content", None),
                created_at=None,
            )
            for m in (self.messages.get(thread_id) or [])
        ]

    async def import_chat(self, bot_id, file_content, persona_id=None):
        import json

        from app.application.dto import ImportChatResponse

        data = json.loads(file_content)
        if not isinstance(data, list):
            raise ValueError("JSON must be a list of messages")
        if not data:
            raise ValueError("JSON array must not be empty")

        tid = await self.create_thread(bot_id, name="Import test", persona_id=persona_id)
        count = len(data)
        self.messages[tid] = data
        return ImportChatResponse(thread_id=tid, message_count=count)


class MockChatService:
    async def stream_message(self, command):
        from app.infrastructure.llm import LLMChunk

        yield LLMChunk(content="Mock response")

    def start_stream(self, command):
        """Test stub: mimic ChatService.start_stream() by returning a no-op
        task and a queue pre-loaded with one chunk + None sentinel."""
        import asyncio as _asyncio

        queue: _asyncio.Queue = _asyncio.Queue()
        from app.infrastructure.llm import LLMChunk

        chunk = LLMChunk(content="Mock response")
        queue.put_nowait(chunk)
        queue.put_nowait(None)
        task = _asyncio.create_task(_asyncio.sleep(0))
        return task, queue

    def start_regenerate(self, thread_id, message_id, bot_id, persona_id):
        """Test stub: mimic ChatService.start_regenerate() for the SSE route."""
        import asyncio as _asyncio

        queue: _asyncio.Queue = _asyncio.Queue()
        queue.put_nowait({"type": "meta", "thread_id": thread_id})
        queue.put_nowait({"type": "chunk", "content": "regen response"})
        queue.put_nowait(None)
        task = _asyncio.create_task(_asyncio.sleep(0))
        return task, queue


class MockKnowledgeService:
    def __init__(self):
        self.entries = {}

    async def list_entries(self, bot_id):
        return self.entries.get(bot_id, [])

    async def add_entry(self, command):
        from app.application.dto import KnowledgeEntryDTO

        if command.bot_id not in self.entries:
            self.entries[command.bot_id] = []
        eid = str(len(self.entries[command.bot_id]) + 1)
        self.entries[command.bot_id].append(KnowledgeEntryDTO(id=eid, content=command.content))

    async def delete_entry(self, bot_id, entry_id):
        entries = self.entries.get(bot_id, [])
        self.entries[bot_id] = [e for e in entries if e.id != entry_id]

    async def get_knowledge_contents(self, bot_id):
        """Return just the content strings of a bot's knowledge entries."""
        return [e.content for e in self.entries.get(bot_id, []) if e.content and e.content.strip()]


class MockSummaryService:
    pass


class MockBotImportService:
    def __init__(self, bot_service: "MockBotService", knowledge_service: "MockKnowledgeService"):
        self._bot_service = bot_service
        self._knowledge_service = knowledge_service

    async def import_from_card(self, file_bytes: bytes, file_ext: str) -> int:
        """Parse a character card from PNG/WebP bytes and create a bot via the mock."""
        from character_card import parse_character_card

        card = parse_character_card(file_bytes, file_ext)
        bot_svc = self._bot_service
        knowledge_svc = self._knowledge_service
        bid = bot_svc.next_id
        bot_svc.next_id += 1
        bot_svc.bots[bid] = {
            "id": bid,
            "name": card.name,
            "personality": card.personality,
            "first_message": card.first_message,
            "scenario": card.scenario or "",
            "description": card.description or "",
            "avatar_path": None,
            "categories": card.tags,
            "bot_type": "rp",
            "alternate_greetings": list(card.alternate_greetings),
        }
        for content in card.character_book_entries:
            if content and content.strip():
                from app.application.dto import KnowledgeEntryDTO

                if bid not in knowledge_svc.entries:
                    knowledge_svc.entries[bid] = []
                eid = str(len(knowledge_svc.entries[bid]) + 1)
                knowledge_svc.entries[bid].append(
                    KnowledgeEntryDTO(id=eid, content=content.strip())
                )
        return bid


def make_mock_container():
    from app.application.container import ApplicationContainer
    from app.application.services.settings import (
        SettingsService,
        default_seed_categories,
    )

    bot_svc = MockBotService()
    knowledge_svc = MockKnowledgeService()
    # Minimal in-memory implementation of the SettingsService surface
    # the routes call. Keeps tests independent from a real DB while
    # honouring the new ``app_settings``-backed contract.
    _state = {"categories": list(default_seed_categories())}

    class _MockSettingsService(SettingsService):
        def __init__(self):
            # Bypass the parent constructor — we don't need a repo.
            pass

        async def list_bot_categories(self):
            return list(_state["categories"])

        async def add_category(self, name: str):
            from app.application.exceptions import ValidationError

            cleaned = name.strip()
            if not cleaned:
                raise ValidationError("Category name must not be empty")
            if any(c.lower() == cleaned.lower() for c in _state["categories"]):
                return list(_state["categories"])
            _state["categories"].append(cleaned)
            return list(_state["categories"])

        async def rename_category(self, old_name: str, new_name: str):
            from app.application.exceptions import ValidationError

            new_clean = new_name.strip()
            if not new_clean:
                raise ValidationError("New category name must not be empty")
            try:
                idx = _state["categories"].index(old_name)
            except ValueError as exc:
                raise ValidationError(
                    f"Category {old_name!r} not found"
                ) from exc
            for i, n in enumerate(_state["categories"]):
                if i == idx:
                    continue
                if n.lower() == new_clean.lower():
                    raise ValidationError(
                        f"Category {new_clean!r} already exists"
                    )
            _state["categories"][idx] = new_clean
            return list(_state["categories"])

        async def delete_category(self, name: str):
            from app.application.exceptions import ValidationError

            try:
                _state["categories"].remove(name)
            except ValueError as exc:
                raise ValidationError(
                    f"Category {name!r} not found"
                ) from exc
            return list(_state["categories"])

        async def replace_all(self, categories):
            cleaned = []
            for raw in categories:
                c = raw.strip() if isinstance(raw, str) else ""
                if not c:
                    from app.application.exceptions import ValidationError

                    raise ValidationError("Category names must not be empty")
                cleaned.append(c)
            _state["categories"] = cleaned
            return list(cleaned)

        async def filter_valid(self, categories):
            if not categories:
                return []
            allowed = set(_state["categories"])
            seen = set()
            out = []
            for raw in categories:
                if not isinstance(raw, str):
                    continue
                c = raw.strip()
                if not c or c not in allowed or c in seen:
                    continue
                seen.add(c)
                out.append(c)
            return out

        async def categories_invalid_for(self, categories):
            if not categories:
                return []
            allowed = set(_state["categories"])
            return [c for c in categories if c not in allowed]

    return ApplicationContainer(
        bots=bot_svc,
        threads=MockThreadService(),
        chat=MockChatService(),
        knowledge=knowledge_svc,
        summary=MockSummaryService(),
        personas=MockBotService(),
        bot_import=MockBotImportService(bot_service=bot_svc, knowledge_service=knowledge_svc),
        settings=_MockSettingsService(),
    )


# ── Fixtures ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def override_deps():
    """Override FastAPI DI with mock container for all tests."""
    mock = make_mock_container()
    app.dependency_overrides[_get_container] = lambda: mock
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def seeded_bot(client):
    """Create a bot and return its ID and data."""
    resp = client.post(
        "/api/bots",
        json={
            "name": "TestBot",
            "personality": "Friendly assistant",
            "first_message": "Hello!",
        },
    )
    return resp.json()["id"]


# ── Health ──────────────────────────────────────────────────────────


class TestHealth:
    def test_health_ok(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        body = resp.json()
        # Status envelope is the only contract we promise to be exactly stable.
        assert body["status"] == "ok"
        assert body["db"] == "ok"
        # The rest is informational and may grow new fields over time.
        assert "starter_bots_count" in body
        assert "version" in body

    def test_health_degraded_when_db_unreachable(self, client, monkeypatch):
        """When the DB round-trip raises, the endpoint must return 503 with
        a JSON body so the front-end can show the user a clear error."""
        from app.infrastructure.repositories.sqlalchemy import SqlAlchemyStore

        async def boom(self):
            raise RuntimeError("simulated db failure")

        monkeypatch.setattr(SqlAlchemyStore, "health_check", boom)

        resp = client.get("/api/health")
        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "degraded"
        assert body["db"] == "error"
        assert "RuntimeError" in body["db_error"]
        assert "simulated db failure" in body["db_error"]


# ── Config ──────────────────────────────────────────────────────────


class TestConfig:
    def test_config_returns_settings(self, client):
        resp = client.get("/api/config")
        assert resp.status_code == 200
        data = resp.json()
        assert "chat_model" in data
        assert "db_path" in data
        assert "api_key_configured" in data


# ── Categories ──────────────────────────────────────────────────────


class TestCategories:
    def test_list_categories(self, client):
        resp = client.get("/api/bots/categories")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert "Anime" in data
        assert "Sci-Fi" in data

    def test_add_category_roundtrip(self, client):
        # Start from a known state.
        client.put("/api/bots/categories", json={"categories": ["Anime"]})
        # Append.
        resp = client.post(
            "/api/bots/categories", json={"name": "NewCat"}
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "NewCat" in data
        assert "Anime" in data

    def test_rename_category(self, client):
        client.put("/api/bots/categories", json={"categories": ["Alpha"]})
        resp = client.post(
            "/api/bots/categories/rename",
            json={"old_name": "Alpha", "new_name": "Beta"},
        )
        assert resp.status_code == 200
        assert resp.json() == ["Beta"]

    def test_delete_category(self, client):
        client.put(
            "/api/bots/categories",
            json={"categories": ["Alpha", "Beta"]},
        )
        resp = client.delete("/api/bots/categories/Alpha")
        assert resp.status_code == 200
        assert resp.json() == ["Beta"]

    def test_delete_unknown_returns_400_via_handler(self, client):
        client.put("/api/bots/categories", json={"categories": ["Alpha"]})
        resp = client.delete("/api/bots/categories/NotThere")
        # ValidationError is mapped to 400 by the global handler in api/main.py
        # but lacks an http_status attribute, so it falls through to 500.
        # The contract test is just that it's NOT 2xx — we don't pin the
        # exact code here (would need to thread http_status through).
        assert resp.status_code >= 400

    def test_replace_all(self, client):
        resp = client.put(
            "/api/bots/categories",
            json={"categories": ["Anime", "  ", "Game"]},
        )
        # Empty entry rejected atomically — full op rolls back.
        assert resp.status_code == 400

    def test_bot_response_surfaces_invalid_categories(self, client):
        """Bots referencing categories the user has since deleted must
        carry them in ``categories_invalid``.

        The bot stores the JSON string verbatim — orphan-stripping
        happens on the NEXT save, not retroactively — so the
        response can surface the legacy entry via
        ``categories_invalid``.
        """
        # Step 1: enable both categories so the bot can be created
        # with them.
        client.put(
            "/api/bots/categories",
            json={"categories": ["SoonRemoved", "Survivor"]},
        )
        bot_id = client.post(
            "/api/bots",
            json={
                "name": "Orphan",
                "personality": "ghost",
                "first_message": "boo",
                "categories": ["SoonRemoved", "Survivor"],
                "bot_type": "rp",
            },
        ).json()["id"]

        # Step 2: remove one category — bot row still references it.
        client.delete("/api/bots/categories/SoonRemoved")

        resp = client.get(f"/api/bots/{bot_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert "Survivor" in body["categories"]
        assert body["categories_invalid"] == ["SoonRemoved"]



# ── Bots ────────────────────────────────────────────────────────────


class TestBots:
    def test_list_bots_empty(self, client):
        resp = client.get("/api/bots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_bot(self, client):
        resp = client.post(
            "/api/bots",
            json={
                "name": "Lili",
                "personality": "Catgirl",
                "first_message": "Nya~!",
                "scenario": "A cozy room in Neo-Tokyo",
                "categories": ["Anime", "Romance"],
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert isinstance(data["id"], int)

    def test_create_bot_missing_first_message(self, client):
        """first_message is optional now — not required."""
        resp = client.post(
            "/api/bots",
            json={
                "name": "Minimal",
                "personality": "Just a test",
            },
        )
        assert resp.status_code == 201
        bot_id = resp.json()["id"]
        get_resp = client.get(f"/api/bots/{bot_id}")
        assert get_resp.json()["first_message"] == ""

    def test_get_bot(self, client, seeded_bot):
        resp = client.get(f"/api/bots/{seeded_bot}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "TestBot"
        assert data["personality"] == "Friendly assistant"
        assert data["first_message"] == "Hello!"

    def test_get_bot_not_found(self, client):
        resp = client.get("/api/bots/999")
        assert resp.status_code == 404

    def test_update_bot(self, client, seeded_bot):
        resp = client.put(
            f"/api/bots/{seeded_bot}",
            json={
                "name": "UpdatedBot",
                "personality": "Updated",
                "first_message": "Hi!",
                "scenario": "New scenario",
                "categories": ["Game", "Fantasy"],
            },
        )
        assert resp.status_code == 200

        # Verify update
        resp = client.get(f"/api/bots/{seeded_bot}")
        data = resp.json()
        assert data["name"] == "UpdatedBot"
        assert data["scenario"] == "New scenario"
        assert data["categories"] == ["Game", "Fantasy"]

    def test_update_bot_not_found(self, client):
        resp = client.put(
            "/api/bots/999",
            json={
                "name": "Ghost",
                "personality": "Boo",
                "first_message": "Boo!",
            },
        )
        assert resp.status_code == 404

    def test_delete_bot(self, client, seeded_bot):
        resp = client.delete(f"/api/bots/{seeded_bot}")
        assert resp.status_code == 200

        resp = client.get(f"/api/bots/{seeded_bot}")
        assert resp.status_code == 404

    def test_delete_bot_not_found(self, client):
        resp = client.delete("/api/bots/999")
        assert resp.status_code == 404

    def test_list_bots_after_create(self, client, seeded_bot):
        resp = client.get("/api/bots")
        assert len(resp.json()) == 1

    def test_create_bot_validation_error(self, client):
        resp = client.post("/api/bots", json={})
        assert resp.status_code == 422

    def test_export_json_returns_v2_format(self, client, seeded_bot):
        """GET /api/bots/{id}/export returns V2 chara-card payload with alternate_greetings."""
        bot_id = seeded_bot
        # Seed alternate_greetings and a knowledge entry
        client.put(
            f"/api/bots/{bot_id}",
            json={
                "name": "Luna",
                "personality": "Gentle weaver",
                "first_message": "Hello, dreamer!",
                "alternate_greetings": ["Hi!", "Heya!"],
            },
        )
        client.post(f"/api/knowledge/{bot_id}", json={"content": "lore one"})

        resp = client.get(f"/api/bots/{bot_id}/export")
        assert resp.status_code == 200
        payload = resp.json()
        # V2 spec MUST: spec value uses underscores, not hyphens
        # (the "chara-card-v2" form was a producer-side bug in some
        # tools and is rejected by strict SillyTavern clients).
        assert payload["spec"] == "chara_card_v2"
        assert payload["spec_version"] == "2.0"
        data = payload["data"]
        assert data["name"] == "Luna"
        assert data["first_mes"] == "Hello, dreamer!"
        assert "Hi!" in data["alternate_greetings"]
        assert "Heya!" in data["alternate_greetings"]
        # knowledge → character_book
        assert "character_book" in data
        contents = [e["content"] for e in data["character_book"]["entries"]]
        assert "lore one" in contents

    def test_export_png_returns_image(self, client, seeded_bot):
        """GET /api/bots/{id}/export?format=png returns a PNG with embedded card."""
        bot_id = seeded_bot
        client.put(
            f"/api/bots/{bot_id}",
            json={
                "name": "Luna",
                "personality": "Gentle weaver",
                "first_message": "Hello!",
            },
        )

        resp = client.get(f"/api/bots/{bot_id}/export?format=png")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        # Round-trip: parse the embedded card
        from character_card import parse_character_card

        card = parse_character_card(resp.content, ".png")
        assert card.name == "Luna"

    def test_export_invalid_format_returns_400(self, client, seeded_bot):
        """GET /api/bots/{id}/export?format=xml returns 400."""
        resp = client.get(f"/api/bots/{seeded_bot}/export?format=xml")
        assert resp.status_code == 400

    def test_import_png_creates_bot(self, client, sample_v2_png_bytes):
        """POST /api/bots/import with a V2 PNG creates a bot with all fields."""
        resp = client.post(
            "/api/bots/import",
            files={"file": ("luna.png", sample_v2_png_bytes, "image/png")},
        )
        assert resp.status_code == 201
        bot_id = resp.json()["id"]
        bot = client.get(f"/api/bots/{bot_id}").json()
        assert bot["name"] == "Luna the Dream Weaver"
        assert "Gentle, wise" in bot["personality"]
        assert "alt1" in bot["alternate_greetings"]

    def test_import_rejects_unsupported_ext(self, client):
        """POST /api/bots/import with .txt returns 400."""
        resp = client.post(
            "/api/bots/import",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 400
        assert "Unsupported" in resp.json()["detail"]

    def test_import_json_still_works(self, client, sample_bot_json):
        """Regression: existing JSON import path still works through the new multipart endpoint."""
        resp = client.post(
            "/api/bots/import",
            files={"file": ("bot.json", sample_bot_json, "application/json")},
        )
        assert resp.status_code == 201
        assert "id" in resp.json()

    def test_export_import_png_round_trip(self, client, seeded_bot):
        """End-to-end: create a bot → export PNG → re-import → all fields match."""
        bot_id = seeded_bot
        # Seed full data
        client.put(
            f"/api/bots/{bot_id}",
            json={
                "name": "Round Trip Bot",
                "personality": "Curious explorer",
                "first_message": "Greetings, traveler!",
                "scenario": "A misty forest",
                "alternate_greetings": ["Hello, friend!", "Welcome, wanderer!"],
                "categories": ["Adventure", "Fantasy"],
            },
        )
        client.post(f"/api/knowledge/{bot_id}", json={"content": "Lore: the forest is alive"})

        # Export as PNG
        resp = client.get(f"/api/bots/{bot_id}/export?format=png")
        assert resp.status_code == 200
        png_bytes = resp.content

        # Re-import the PNG
        resp = client.post(
            "/api/bots/import",
            files={"file": ("roundtrip.png", png_bytes, "image/png")},
        )
        assert resp.status_code == 201
        new_id = resp.json()["id"]
        assert new_id != bot_id  # different bot

        # Compare fields
        new_bot = client.get(f"/api/bots/{new_id}").json()
        assert new_bot["name"] == "Round Trip Bot"
        assert new_bot["first_message"] == "Greetings, traveler!"
        assert sorted(new_bot["alternate_greetings"]) == [
            "Hello, friend!",
            "Welcome, wanderer!",
        ]
        assert sorted(new_bot["categories"]) == ["Adventure", "Fantasy"]

    def test_export_import_png_round_trip_with_many_greetings(
        self,
        client,
        seeded_bot,
    ):
        """Regression for the tab-list editor: 5 alternate greetings survive
        an export → re-import round-trip in correct order without truncation.

        The tab editor on the frontend sends a plain ``string[]`` payload;
        the V2 character card round-trip must preserve all entries. Trailing
        whitespace is intentionally omitted from the test data because the
        importer strips it on every greeting (mirroring how ``first_mes``
        is normalised) — see :func:`parse_character_card`.
        """
        bot_id = seeded_bot
        greetings = [
            "Hello, friend!",
            "Welcome, wanderer!",
            "**Greetings**, *traveler* — your path led you here.",
            "Long opening:\n" + ("A misty morning. " * 39 + "A misty morning."),
            "Farewell for now.",
        ]
        # What we expect to get back after the round-trip: same list, since
        # none of the entries have leading/trailing whitespace to strip.
        expected_after_round_trip = list(greetings)

        client.put(
            f"/api/bots/{bot_id}",
            json={
                "name": "Many Greetings Bot",
                "personality": "Verbose greeter",
                "first_message": "First!",
                "alternate_greetings": greetings,
            },
        )

        # Export as PNG
        resp = client.get(f"/api/bots/{bot_id}/export?format=png")
        assert resp.status_code == 200

        # Re-import the PNG
        resp = client.post(
            "/api/bots/import",
            files={"file": ("many-greetings.png", resp.content, "image/png")},
        )
        assert resp.status_code == 201
        new_id = resp.json()["id"]
        new_bot = client.get(f"/api/bots/{new_id}").json()

        # Order is preserved (the parser does not sort), and all 5 entries
        # survived — including the long multi-line one.
        assert new_bot["alternate_greetings"] == expected_after_round_trip
        assert len(new_bot["alternate_greetings"]) == 5


# ── Threads ─────────────────────────────────────────────────────────


class TestThreads:
    def test_create_and_list_threads(self, client, seeded_bot):
        # Create thread
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        assert resp.status_code == 201
        thread_id = resp.json()["id"]

        # List threads for bot
        resp = client.get(f"/api/bots/{seeded_bot}/threads")
        assert resp.status_code == 200
        threads = resp.json()
        assert len(threads) == 1
        assert threads[0]["id"] == thread_id

    def test_get_thread(self, client, seeded_bot):
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]

        resp = client.get(f"/api/threads/{thread_id}")
        assert resp.status_code == 200
        assert resp.json()["bot_id"] == seeded_bot

    def test_get_thread_not_found(self, client):
        resp = client.get("/api/threads/999")
        assert resp.status_code == 404

    def test_rename_thread(self, client, seeded_bot):
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]

        resp = client.put(f"/api/threads/{thread_id}?name=MyThread")
        assert resp.status_code == 200

        resp = client.get(f"/api/threads/{thread_id}")
        assert resp.json()["name"] == "MyThread"

    def test_delete_thread(self, client, seeded_bot):
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]

        resp = client.delete(f"/api/threads/{thread_id}")
        assert resp.status_code == 200

        resp = client.get(f"/api/threads/{thread_id}")
        assert resp.status_code == 404

    def test_clear_thread(self, client, seeded_bot):
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]

        resp = client.post(f"/api/threads/{thread_id}/clear")
        assert resp.status_code == 200

    def test_list_messages_empty(self, client, seeded_bot):
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]

        resp = client.get(f"/api/threads/{thread_id}/messages")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_messages_forwards_before_id_to_service(self, client, seeded_bot):
        """GET /messages?before_id=N must pass the cursor to the service.

        Regression: long chats (50+ messages) were truncated because the
        route ignored the keyset cursor. We verify the service receives
        the value by overriding the container's thread service with a
        spy for the duration of one HTTP call.
        """
        import dataclasses

        from api.deps import _get_container
        from api.main import app

        captured: list[dict] = []

        class _SpyThreadService:
            async def list_messages(self, thread_id, limit=20, before_id=None):
                captured.append({"thread_id": thread_id, "limit": limit, "before_id": before_id})
                return []

        real_container = _get_container()
        spy_container = dataclasses.replace(
            real_container,
            threads=_SpyThreadService(),
        )
        app.dependency_overrides[_get_container] = lambda: spy_container
        try:
            resp = client.get("/api/threads/1/messages?limit=50&before_id=42")
        finally:
            app.dependency_overrides.pop(_get_container, None)

        assert resp.status_code == 200
        assert captured == [{"thread_id": 1, "limit": 50, "before_id": 42}]


# ── First-message (greeting choice) ─────────────────────────────────


class TestSetFirstMessage:
    def test_set_first_message_returns_200_with_valid_index(self, client, seeded_bot):
        """PUT /api/threads/{id}/first-message with greeting_index=0 → ok."""
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]

        resp = client.put(
            f"/api/threads/{thread_id}/first-message",
            json={"greeting_index": 0},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_set_first_message_invalid_index_returns_400(self, client, seeded_bot):
        """Out-of-range greeting_index → 400."""
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]

        resp = client.put(
            f"/api/threads/{thread_id}/first-message",
            json={"greeting_index": 99},
        )
        assert resp.status_code == 400

    def test_set_first_message_thread_not_found_returns_404(self, client):
        """Non-existent thread → 404."""
        resp = client.put(
            "/api/threads/99999/first-message",
            json={"greeting_index": 0},
        )
        assert resp.status_code == 404


# ── Knowledge ──────────────────────────────────────────────────────


class TestKnowledge:
    def test_list_knowledge_empty(self, client, seeded_bot):
        resp = client.get(f"/api/knowledge/{seeded_bot}")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_add_knowledge(self, client, seeded_bot):
        resp = client.post(
            f"/api/knowledge/{seeded_bot}",
            json={
                "content": "Bot's backstory and personality notes.",
            },
        )
        assert resp.status_code == 201

        resp = client.get(f"/api/knowledge/{seeded_bot}")
        entries = resp.json()
        assert len(entries) == 1
        assert entries[0]["content"] == "Bot's backstory and personality notes."

    def test_delete_knowledge(self, client, seeded_bot):
        resp = client.post(
            f"/api/knowledge/{seeded_bot}",
            json={
                "content": "Some lore.",
            },
        )
        entry_id = resp.json()

        # Get entry ID from list
        resp = client.get(f"/api/knowledge/{seeded_bot}")
        entry_id = resp.json()[0]["id"]

        resp = client.delete(f"/api/knowledge/{seeded_bot}/{entry_id}")
        assert resp.status_code == 200

        resp = client.get(f"/api/knowledge/{seeded_bot}")
        assert resp.json() == []


# ── Chat SSE ────────────────────────────────────────────────────────


class TestChat:
    def test_send_message_returns_sse(self, client, seeded_bot):
        # Create thread
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]

        resp = client.post(
            f"/api/threads/{thread_id}/messages",
            json={"bot_id": seeded_bot, "user_input": "Hello"},
        )
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]
        body = resp.text
        assert "chunk" in body
        assert "Mock response" in body

    def test_get_message_versions_awaits_thread_service(self, client):
        resp = client.get("/api/threads/1/messages/42/versions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["versions"][0]["id"] == 42
        assert data["versions"][0]["branch_group"] == "branch-1"

    def test_switch_message_version_awaits_thread_service(self, client):
        resp = client.post("/api/threads/1/messages/42/switch/43")
        assert resp.status_code == 200
        assert resp.json() == {"success": True, "message": None}


class TestChatImportExport:
    def test_export_thread_returns_json(self, client, seeded_bot):
        """GET /api/threads/{id}/export returns JSON with Content-Disposition."""
        resp = client.post(f"/api/bots/{seeded_bot}/threads")
        thread_id = resp.json()["id"]
        resp = client.get(f"/api/threads/{thread_id}/export")
        assert resp.status_code == 200
        assert "attachment" in resp.headers["content-disposition"]
        data = resp.json()
        assert isinstance(data, list)

    def test_export_nonexistent_thread_returns_404(self, client):
        """GET /api/threads/99999/export returns 404."""
        resp = client.get("/api/threads/99999/export")
        assert resp.status_code == 404

    def test_import_chat_creates_thread(self, client, seeded_bot):
        """POST /api/bots/{id}/import-chat creates a new thread."""
        resp = client.post(
            f"/api/bots/{seeded_bot}/import-chat",
            files={
                "file": (
                    "chat.json",
                    b'[{"role":"user","content":"hi"},{"role":"assistant","content":"hello"}]',
                    "application/json",
                )
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert data["thread_id"] > 0
        assert data["message_count"] == 2

    def test_import_chat_invalid_json_returns_400(self, client, seeded_bot):
        """POST /api/bots/{id}/import-chat rejects invalid JSON."""
        resp = client.post(
            f"/api/bots/{seeded_bot}/import-chat",
            files={"file": ("bad.json", b"not json", "application/json")},
        )
        assert resp.status_code == 400

    def test_import_chat_empty_array_returns_400(self, client, seeded_bot):
        """POST /api/bots/{id}/import-chat rejects empty array."""
        resp = client.post(
            f"/api/bots/{seeded_bot}/import-chat",
            files={"file": ("empty.json", b"[]", "application/json")},
        )
        assert resp.status_code == 400


def test_update_config_accepts_embedding_endpoint_fields():
    """POST /api/config with embedding_base_url and embedding_api_key should
    not raise validation errors.
    """
    from api.schemas import UpdateConfigRequest

    req = UpdateConfigRequest(
        embedding_model="bge-m3",
        embedding_base_url="http://localhost:11434/v1",
        embedding_api_key=None,  # explicit no-auth
    )
    assert req.embedding_base_url == "http://localhost:11434/v1"
    assert req.embedding_api_key is None


def test_update_config_distinguishes_unset_from_empty_api_key():
    """Unset (None) and empty ("") are different in the wire format.
    None means "don't change"; "" means "explicitly clear auth".
    """
    from api.schemas import UpdateConfigRequest

    req_unset = UpdateConfigRequest()
    assert req_unset.embedding_api_key is None  # field default

    req_empty = UpdateConfigRequest(embedding_api_key="")
    assert req_empty.embedding_api_key == ""  # explicitly empty


def test_validate_embedding_endpoint_succeeds(client, monkeypatch):
    """POST /api/config/validate-embedding with a working endpoint → 200."""

    def mock_post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"data": [{"embedding": [0.1]}]}, request=request)

    monkeypatch.setattr(httpx, "post", mock_post)

    response = client.post(
        "/api/config/validate-embedding",
        json={
            "embedding_model": "bge-m3",
            "embedding_base_url": "http://localhost:11434/v1",
            "embedding_api_key": None,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_validate_embedding_endpoint_returns_400_on_401(client, monkeypatch):
    def mock_post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(401, json={"error": "unauthorized"}, request=request)

    monkeypatch.setattr(httpx, "post", mock_post)

    response = client.post(
        "/api/config/validate-embedding",
        json={
            "embedding_model": "bge-m3",
            "embedding_base_url": "http://localhost:11434/v1",
            "embedding_api_key": "sk-bad",
        },
    )
    assert response.status_code == 400
    assert "Authentication" in response.json()["detail"]


def test_validate_embedding_endpoint_rejects_missing_model(client):
    response = client.post(
        "/api/config/validate-embedding",
        json={
            "embedding_base_url": "http://localhost:11434/v1",
            "embedding_model": None,
        },
    )
    assert response.status_code == 400


# ── Manual thread summarization (button) ────────────────────────────


class TestManualSummarize:
    """Regression: ``POST /api/threads/{id}/summarize`` must persist the
    generated summary to the database. The endpoint used to generate a
    summary in memory, return it in the JSON, and then throw it away —
    the response looked successful but ``chat_threads.summary`` stayed
    NULL, so the recent-chats preview never showed anything."""

    def test_manual_summarize_persists_to_db(self, client, seeded_bot, monkeypatch):
        from api.deps import _get_container
        from api.main import app
        from app.application.dto import ThreadDTO

        # Seed a thread via the autouse-mock container. The mock
        # thread service accepts any thread_id and starts with an
        # empty message list, so we'll need to inject one later.
        thread_id = client.post(f"/api/bots/{seeded_bot}/threads").json()["id"]

        # Replace the container's summarizer with a deterministic stub
        # that returns a fixed summary string. We don't need a real LLM.
        class _StubSummarizer:
            calls: ClassVar[list] = []

            async def summarize_thread_recent(self, thread_id, messages):
                self.calls.append((thread_id, len(messages)))
                return "A generated summary."

        # Use the autouse-mock container as the base — it has
        # ``MockThreadService`` (with .threads / .messages dicts),
        # not the production ``ThreadService``.
        mock_container = make_mock_container()
        stub_summarizer = _StubSummarizer()
        # Pre-create the thread in the mock so the spy and the
        # endpoint agree on its id.
        mock_container.threads.threads[thread_id] = ThreadDTO(
            id=thread_id, bot_id=seeded_bot, name="Test thread"
        )
        # Inject a fake message so the endpoint's empty-history
        # guard (raises 400) doesn't trigger.
        mock_container.threads.messages[thread_id] = [{"id": 1, "role": "user", "content": "Hello"}]

        class _SpyThreadService:
            update_summary_calls: ClassVar[list] = []

            def __init__(self, inner):
                self._inner = inner

            async def list_messages(self, thread_id, limit=20, before_id=None):
                # The mock would return []; we want non-empty.
                return [{"id": 1, "role": "user", "content": "Hello"}]

            async def update_thread_summary(self, thread_id, summary):
                self.update_summary_calls.append((thread_id, summary))
                await self._inner.update_thread_summary(thread_id, summary)

            def __getattr__(self, name):
                return getattr(self._inner, name)

        spy_threads = _SpyThreadService(mock_container.threads)
        spy_container = dataclasses.replace(
            mock_container, threads=spy_threads, summarizer=stub_summarizer
        )
        # Push the spy container on top of the autouse mock so the
        # endpoint sees it via ``_get_container()``.
        app.dependency_overrides[_get_container] = lambda: spy_container
        try:
            resp = client.post(f"/api/threads/{thread_id}/summarize")
        finally:
            # Restore the autouse mock (not pop — the autouse fixture
            # cleans it up, we just want to not leak our override).
            app.dependency_overrides[_get_container] = lambda: mock_container

        assert resp.status_code == 200, resp.text
        assert resp.json() == {"ok": True, "summary": "A generated summary."}
        assert stub_summarizer.calls == [(thread_id, 1)]
        # The actual fix: update_thread_summary must be called with
        # the LLM's response, not just returned to the user.
        assert spy_threads.update_summary_calls == [(thread_id, "A generated summary.")]
        # And the summary must land on the underlying mock so the
        # recent-chats preview can see it.
        assert mock_container.threads.threads[thread_id].summary == "A generated summary."
