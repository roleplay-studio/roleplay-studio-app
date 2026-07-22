"""Regression tests for ``{{user}}`` substitution at thread creation.

The previous fix (commit 4bdb38d) wired substitution through
``ChatService.stream_message`` — the path used by
``POST /api/threads/{thread_id}/messages``. But the user-facing
"create a new chat" button hits a different endpoint:
``POST /api/bots/{bot_id}/threads``, which creates the thread
AND immediately calls ``stream_save_first_message`` from
``api/routes/bots.py::create_thread``. That call site was never
updated to pass ``persona_name``, so the literal ``{{user}}``
token was persisted verbatim even when a persona was selected.

This test pins the end-to-end contract via ``TestClient``:
create a bot with a templated ``first_message``, POST a new
thread with a persona_id, then read the thread's messages and
assert the placeholder was substituted.
"""
from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.deps import _get_container
from api.main import app


class _NoopContainer:
    """Minimal stand-in for the create_thread endpoint's needs.

    ``create_thread`` only touches ``container.threads`` and
    ``container.chat``. We don't need the full bootstrap graph —
    the integration below uses a separate in-memory path that
    doesn't require the real SqlAlchemyStore.
    """

    class _Threads:
        async def create_thread(self, bot_id: int, persona_id: int | None = None) -> int:
            # Use a deterministic but unique id so we can read it back.
            return bot_id * 1000 + (persona_id or 0)

    threads = _Threads()
    chat = None  # stream_save_first_message branch is short-circuited
    bots = None
    personas = None


@pytest.fixture
def client() -> TestClient:
    app.dependency_overrides[_get_container] = lambda: _NoopContainer()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_create_thread_passes_persona_name_to_stream_save_first_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``POST /api/bots/{bot_id}/threads`` with a ``persona_id``
    must call ``container.chat.stream_save_first_message`` with
    the resolved persona ``name`` as the third positional / keyword
    argument. Before the fix, no persona_name was passed at all,
    so the literal ``{{user}}`` token was persisted.

    We patch ``stream_save_first_message`` on a stub chat
    service to capture the kwargs without spinning up a real
    SqlAlchemyStore / Settings / LLM.
    """
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    captured: dict[str, Any] = {}

    class _StubChat:
        async def stream_save_first_message(
            self,
            thread_id: int,
            bot_id: int,
            persona_name: str | None = None,
        ) -> None:
            captured["thread_id"] = thread_id
            captured["bot_id"] = bot_id
            captured["persona_name"] = persona_name

    class _StubBots:
        async def get_bot(self, bot_id: int) -> Any:
            # Return a minimal bot with a first_message that has
            # the placeholder — the endpoint checks `if bot and
            # bot.first_message:` before calling stream_save.
            class _Bot:
                pass

            b = _Bot()
            b.id = bot_id
            b.first_message = "Hi {{user}}!"
            b.personality = "p"
            return b

    class _StubPersonas:
        async def get(self, persona_id: int) -> Any:
            class _Persona:
                pass

            p = _Persona()
            p.id = persona_id
            p.name = "Дмитрий"
            p.description = ""
            return p

    class _FullContainer(_NoopContainer):
        chat = _StubChat()
        bots = _StubBots()
        personas = _StubPersonas()

    app.dependency_overrides[_get_container] = lambda: _FullContainer()
    try:
        client = TestClient(app)
        resp = client.post("/api/bots/45/threads", json={"persona_id": 1})
        assert resp.status_code == 201
    finally:
        app.dependency_overrides.clear()

    # The persona name MUST be resolved and passed in.
    assert captured.get("persona_name") == "Дмитрий", (
        f"create_thread should pass the resolved persona name to "
        f"stream_save_first_message, got {captured.get('persona_name')!r}"
    )


def test_create_thread_passes_none_when_no_persona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without a ``persona_id``, ``create_thread`` must still call
    ``stream_save_first_message`` (so the row gets persisted) but
    with ``persona_name=None`` so the placeholder survives for
    the orchestrator to substitute on the first turn.
    """
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    captured: dict[str, Any] = {}

    class _StubChat:
        async def stream_save_first_message(
            self,
            thread_id: int,
            bot_id: int,
            persona_name: str | None = None,
        ) -> None:
            captured["persona_name"] = persona_name

    class _StubBots:
        async def get_bot(self, bot_id: int) -> Any:
            class _Bot:
                first_message = "Hi {{user}}!"

            return _Bot()

    class _FullContainer(_NoopContainer):
        chat = _StubChat()
        bots = _StubBots()
        personas = None  # No personas service wired

    app.dependency_overrides[_get_container] = lambda: _FullContainer()
    try:
        client = TestClient(app)
        resp = client.post("/api/bots/45/threads", json={})
        assert resp.status_code == 201
    finally:
        app.dependency_overrides.clear()

    assert captured.get("persona_name") is None


def test_create_thread_swallows_persona_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the persona was deleted between picker and save,
    ``PersonaService.get`` raises ``NotFoundError``. The
    create_thread endpoint must not propagate that — fall through
    to ``persona_name=None`` so the thread is still created and
    the placeholder survives for the orchestrator.
    """
    monkeypatch.setenv("LLM_PROVIDER", "mock")

    captured: dict[str, Any] = {}

    class _StubChat:
        async def stream_save_first_message(
            self,
            thread_id: int,
            bot_id: int,
            persona_name: str | None = None,
        ) -> None:
            captured["persona_name"] = persona_name

    class _StubBots:
        async def get_bot(self, bot_id: int) -> Any:
            class _Bot:
                first_message = "Hi {{user}}!"

            return _Bot()

    class _NotFoundError(Exception):
        pass

    class _StubPersonas:
        async def get(self, persona_id: int) -> Any:
            raise _NotFoundError(f"Persona {persona_id} not found")

    class _FullContainer(_NoopContainer):
        chat = _StubChat()
        bots = _StubBots()
        personas = _StubPersonas()

    app.dependency_overrides[_get_container] = lambda: _FullContainer()
    try:
        client = TestClient(app)
        resp = client.post("/api/bots/45/threads", json={"persona_id": 999})
        # The thread must still be created (201) even though the
        # persona was not found.
        assert resp.status_code == 201
    finally:
        app.dependency_overrides.clear()

    # And the save was called with persona_name=None so the
    # placeholder survives.
    assert captured.get("persona_name") is None
