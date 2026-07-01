"""Tests for the bot update flow — covers frontend API contract."""

import pytest
from fastapi.testclient import TestClient

from api.deps import _get_container
from api.main import app


class MockBotService:
    def __init__(self):
        self.bots = {}
        self.next_id = 1

    async def create_bot(self, command):
        bot_id = self.next_id
        self.next_id += 1
        self.bots[bot_id] = {
            "id": bot_id,
            "name": command.name,
            "personality": command.personality,
            "first_message": command.first_message,
            "scenario": command.scenario or "",
            "description": getattr(command, "description", ""),
            "avatar_path": command.avatar_path,
            "categories": command.categories or [],
            "bot_type": getattr(command, "bot_type", "rp"),
            "alternate_greetings": getattr(command, "alternate_greetings", []),
        }
        return bot_id

    def _to_obj(self, data):
        from types import SimpleNamespace

        return SimpleNamespace(**data)

    async def get_bot(self, bot_id):
        if bot_id not in self.bots:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Bot {bot_id} was not found")
        return self._to_obj(self.bots[bot_id])

    async def list_bots(self):
        return [self._to_obj(d) for d in self.bots.values()]

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
                "avatar_path": command.avatar_path,
                "categories": command.categories or [],
                "bot_type": getattr(command, "bot_type", "rp"),
                "alternate_greetings": getattr(command, "alternate_greetings", []),
            }
        )

    async def delete_bot(self, bot_id):
        if bot_id not in self.bots:
            from app.application.exceptions import NotFoundError

            raise NotFoundError(f"Bot {bot_id} was not found")
        del self.bots[bot_id]

    async def list_bot_scenarios(self, bot_id):
        return []

    async def get_bot_with_count(self, bot_id):
        """Return (bot_obj, thread_count) or raise NotFoundError."""
        bot = await self.get_bot(bot_id)
        return bot, 0

    async def list_bots_with_counts(self):
        """Return list of (bot_obj, thread_count) tuples."""
        return [(self._to_obj(d), 0) for d in self.bots.values()]


class MockThreadService:
    def __init__(self):
        self.threads = {}
        self.next_id = 1

    async def create_thread(self, bot_id, name="Новая беседа"):
        tid = self.next_id
        self.next_id += 1
        from app.application.dto import ThreadDTO

        self.threads[tid] = ThreadDTO(id=tid, bot_id=bot_id, name=name)
        return tid

    async def get_thread(self, thread_id):
        return self.threads.get(thread_id)

    async def list_threads(self, bot_id):
        return [t for t in self.threads.values() if t.bot_id == bot_id]

    async def list_for_bot(self, bot_id):
        return await self.list_threads(bot_id)

    async def rename_thread(self, thread_id, name):
        if thread_id in self.threads:
            self.threads[thread_id].name = name

    async def delete_thread(self, thread_id):
        self.threads.pop(thread_id, None)

    async def clear_conversation(self, thread_id):
        pass

    async def list_messages(self, thread_id, limit=20):
        return []

    async def save_assistant_message(self, thread_id, content):
        pass


class MockChatService:
    pass


class MockKnowledgeService:
    def __init__(self):
        self.entries = {}

    def list_entries(self, bot_id):
        return []

    def add_entry(self, command):
        pass

    def search(self, bot_id, query, top_k=3):
        return []

    def delete_entry(self, bot_id, entry_id):
        pass


class MockSummaryService:
    pass


def make_mock_container():
    from app.application.container import ApplicationContainer

    return ApplicationContainer(
        bots=MockBotService(),
        threads=MockThreadService(),
        chat=MockChatService(),
        knowledge=MockKnowledgeService(),
        summary=MockSummaryService(),
        personas=MockBotService(),
    )


@pytest.fixture(autouse=True)
def override_deps():
    mock = make_mock_container()
    app.dependency_overrides[_get_container] = lambda: mock
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def seeded_bot(client):
    resp = client.post(
        "/api/bots",
        json={
            "name": "TestBot",
            "personality": "Friendly",
            "first_message": "Hello!",
        },
    )
    return resp.json()["id"]


def test_create_and_update_bot_full_cycle(client, seeded_bot):
    """Simulate the frontend flow: create → edit → verify changes."""
    bot_id = seeded_bot

    # 1. Get the bot (verify created)
    get_resp = client.get(f"/api/bots/{bot_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "TestBot"

    # 2. Update the bot (as BotEditPage does — no bot_id in body!)
    update_resp = client.put(
        f"/api/bots/{bot_id}",
        json={
            "name": "UpdatedBot",
            "personality": "Grumpy cat",
            "first_message": "What do you want?",
            "scenario": "A dark alley",
            "avatar_path": None,
            "categories": ["Fantasy"],
        },
    )
    assert update_resp.status_code == 200, f"Update failed: {update_resp.text}"
    assert update_resp.json()["ok"] is True

    # 3. Verify changes persisted
    get_resp2 = client.get(f"/api/bots/{bot_id}")
    assert get_resp2.status_code == 200
    data = get_resp2.json()
    assert data["name"] == "UpdatedBot"
    assert data["personality"] == "Grumpy cat"
    assert data["first_message"] == "What do you want?"
    assert data["scenario"] == "A dark alley"
    assert data["categories"] == ["Fantasy"]

    # 4. Update with minimal fields only
    update_resp3 = client.put(
        f"/api/bots/{bot_id}",
        json={
            "name": "Minimal",
            "personality": "Quiet",
            "first_message": "...",
        },
    )
    assert update_resp3.status_code == 200, f"Minimal update failed: {update_resp3.text}"

    get_resp3 = client.get(f"/api/bots/{bot_id}")
    assert get_resp3.status_code == 200
    assert get_resp3.json()["name"] == "Minimal"
    assert get_resp3.json()["scenario"] == ""


def test_update_bot_not_found(client):
    """Update non-existent bot returns 404."""
    resp = client.put(
        "/api/bots/99999",
        json={
            "name": "Ghost",
            "personality": "Boo",
            "first_message": "I'm dead",
        },
    )
    assert resp.status_code == 404


def test_update_bot_validation_error(client, seeded_bot):
    """Missing required fields returns 422."""
    bot_id = seeded_bot

    resp = client.put(
        f"/api/bots/{bot_id}",
        json={
            "name": "",
            "personality": "Test",
            "first_message": "Test",
        },
    )
    assert resp.status_code == 422


def test_create_bot_with_alternate_greetings_persists(client):
    """alternate_greetings is persisted on create and returned by GET."""
    create_resp = client.post(
        "/api/bots",
        json={
            "name": "GreetingBot",
            "personality": "Cheerful",
            "first_message": "Hello!",
            "alternate_greetings": ["a", "b"],
        },
    )
    assert create_resp.status_code == 201
    bot_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/bots/{bot_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["alternate_greetings"] == ["a", "b"]


def test_create_bot_with_empty_alternate_greetings_persists(client):
    """A bot can be created with only a first_message and no alternates.

    This is the unified-editor's default state: the editor starts with a
    single greeting (index 0 = first_message) and the user has not added
    any alternates yet. The backend must accept and return ``[]`` for
    ``alternate_greetings`` rather than 422-ing the request.
    """
    create_resp = client.post(
        "/api/bots",
        json={
            "name": "OnlyFirst",
            "personality": "Cheerful",
            "first_message": "Just the first!",
            "alternate_greetings": [],
        },
    )
    assert create_resp.status_code == 201
    bot_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/bots/{bot_id}")
    assert get_resp.status_code == 200
    body = get_resp.json()
    assert body["first_message"] == "Just the first!"
    assert body["alternate_greetings"] == []
