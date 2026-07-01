"""Tests for fire-and-forget summarization in /api/threads/{id}/messages.

Regression: ``run_summarization`` was scheduled via FastAPI's
``BackgroundTasks`` which BLOCKS the HTTP response until the
summarization completes. The chat UI therefore sees a multi-second
``loading`` state *after* the LLM has already finished streaming
its response — measured at ~6.7s for a 7-message batch on the
real DeepSeek backend.

After the fix, ``run_summarization`` is launched as a detached
``asyncio.create_task`` and the route returns immediately after
the SSE stream finishes. The HTTP response is delivered as soon
as the LLM is done, not after the background summarization.

These tests are functional: they patch the dependency-overridden
``container.chat`` to install a slow stub summarizer, then time
how long the full ``POST /api/threads/{id}/messages`` request
takes to return. Pre-fix: ~stub_delay. Post-fix: << stub_delay.
"""

from __future__ import annotations

import asyncio
import dataclasses
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient

from api.deps import _get_container
from api.main import app

SLOW_DELAY = 1.5  # seconds — long enough to detect blocking vs. fire-and-forget


# ── Stubs ──────────────────────────────────────────────────────────────


def _make_stub_chat_with_slow_summarizer(calls_holder: list[int]):
    """Build a ChatService-compatible object with a slow run_summarization.

    ApplicationContainer is a frozen dataclass, so we use dataclasses.replace
    to swap in our stub. The route only touches ``run_summarization`` and
    ``start_stream`` — the rest of the ChatService surface is irrelevant
    for this test.
    """
    from tests.test_api import make_mock_container

    container = make_mock_container()

    async def slow_run_summarization(tid: int) -> None:
        calls_holder.append(tid)
        await asyncio.sleep(SLOW_DELAY)

    # Replace chat with a stub that has the slow summarization
    stub_chat = SimpleNamespace(
        run_summarization=slow_run_summarization,
        start_stream=container.chat.start_stream,
    )
    new_container = dataclasses.replace(container, chat=stub_chat, summarizer=SimpleNamespace())
    return new_container


# ── Tests ──────────────────────────────────────────────────────────────


def test_summarization_does_not_block_http_response():
    """POST /messages must return << SLOW_DELAY after the SSE stream finishes,
    even when summarization is slow.

    Pre-fix (BackgroundTasks): the request takes ~SLOW_DELAY.
    Post-fix (asyncio.create_task): the request returns almost immediately.
    """
    calls_holder: list[int] = []
    container = _make_stub_chat_with_slow_summarizer(calls_holder)
    app.dependency_overrides[_get_container] = lambda: container

    try:
        client = TestClient(app)
        bot_id = client.post(
            "/api/bots",
            json={"name": "stub", "personality": "p", "first_message": "Hi!"},
        ).json()["id"]
        thread_id = client.post(f"/api/bots/{bot_id}/threads").json()["id"]

        t0 = time.perf_counter()
        resp = client.post(
            f"/api/threads/{thread_id}/messages",
            json={"bot_id": bot_id, "user_input": "hi"},
        )
        elapsed = time.perf_counter() - t0

        assert resp.status_code == 200
        # Allow some slack for SSE setup, but must be much less than SLOW_DELAY
        # (we'd see exactly SLOW_DELAY if BackgroundTasks were still in use).
        assert elapsed < SLOW_DELAY * 0.5, (
            f"HTTP response took {elapsed:.2f}s — summarization is still "
            f"blocking the response (SLOW_DELAY={SLOW_DELAY}s)"
        )
        # And the summarization function was actually scheduled.
        assert calls_holder == [thread_id], f"expected one call for {thread_id}, got {calls_holder}"
    finally:
        app.dependency_overrides.clear()


def test_summarization_actually_runs_in_background():
    """Fire-and-forget must still call run_summarization — it just
    shouldn't block the response. We wait for the background task
    to finish and confirm it ran exactly once.
    """
    calls_holder: list[int] = []
    container = _make_stub_chat_with_slow_summarizer(calls_holder)

    # Override SLOW_DELAY for this test by injecting a faster closure
    async def fast_run_summarization(tid: int) -> None:
        calls_holder.append(tid)
        await asyncio.sleep(0.3)

    stub_chat = SimpleNamespace(
        run_summarization=fast_run_summarization,
        start_stream=container.chat.start_stream,
    )
    container = dataclasses.replace(container, chat=stub_chat, summarizer=SimpleNamespace())
    app.dependency_overrides[_get_container] = lambda: container

    try:
        client = TestClient(app)
        bot_id = client.post(
            "/api/bots",
            json={"name": "bg", "personality": "p", "first_message": "Hi!"},
        ).json()["id"]
        thread_id = client.post(f"/api/bots/{bot_id}/threads").json()["id"]

        resp = client.post(
            f"/api/threads/{thread_id}/messages",
            json={"bot_id": bot_id, "user_input": "hi"},
        )
        assert resp.status_code == 200
        # Background task should complete within ~1s.
        # TestClient is sync; sleep briefly to let the event loop finish.
        time.sleep(0.6)
        assert calls_holder == [thread_id], (
            f"background summarization did not run, calls={calls_holder}"
        )
    finally:
        app.dependency_overrides.clear()
