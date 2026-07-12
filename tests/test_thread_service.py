"""Tests for ThreadService.set_first_message (Task 3).

Verifies that the service overwrites the first assistant message of a
thread with the greeting at the given index. Used after the user picks a
greeting in the UI (alternate_greetings).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.application.dto import MessageDTO
from app.application.services.thread import ThreadService


def _make_bot(bot_id: int = 1) -> SimpleNamespace:
    return SimpleNamespace(
        id=bot_id,
        first_message="Hello there!",
        alternate_greetings=["Hi friend!", "Greetings, traveler."],
    )


class FakeMessageRepo:
    def __init__(self, first_assistant: MessageDTO | None = None) -> None:
        self._first = first_assistant
        self.updates: list[tuple[int, str]] = []

    async def get_first_assistant(self, thread_id: int) -> MessageDTO | None:
        return self._first

    async def save_first_assistant_if_absent(self, thread_id, content):
        # RC1.2 stub — not exercised in this test file.
        return False

    async def update_content(self, message_id: int, content: str) -> None:
        self.updates.append((message_id, content))


class FakeThreadRepo:
    def __init__(self) -> None:
        self.pending: list[tuple[int, str]] = []

    async def set_pending_greeting(self, thread_id: int, content: str) -> None:
        self.pending.append((thread_id, content))


@pytest.mark.asyncio
async def test_set_first_message_updates_existing_first_assistant_message() -> None:
    """When a first assistant message exists, overwrite its content with the chosen greeting.

    greeting_index=1 maps to alternate_greetings[0] (index 0 is bot.first_message).
    """
    existing = MessageDTO(id=99, role="assistant", content="Old greeting")
    msgs = FakeMessageRepo(first_assistant=existing)
    threads = FakeThreadRepo()
    bots = AsyncMock()
    bots.get = AsyncMock(return_value=_make_bot())

    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]
    svc._bots = bots  # inject for the test

    await svc.set_first_message(thread_id=7, bot_id=1, greeting_index=1)

    assert msgs.updates == [(99, "Hi friend!")]
    assert threads.pending == []


@pytest.mark.asyncio
async def test_set_first_message_index_zero_picks_first_message() -> None:
    """greeting_index=0 picks bot.first_message (not alternate_greetings[0])."""
    existing = MessageDTO(id=42, role="assistant", content="placeholder")
    msgs = FakeMessageRepo(first_assistant=existing)
    threads = FakeThreadRepo()
    bots = AsyncMock()
    bots.get = AsyncMock(return_value=_make_bot())

    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]
    svc._bots = bots

    await svc.set_first_message(thread_id=1, bot_id=1, greeting_index=0)

    assert msgs.updates == [(42, "Hello there!")]


@pytest.mark.asyncio
async def test_set_first_message_no_message_yet_stores_pending_greeting() -> None:
    """When the thread has no assistant message yet, store the chosen greeting as pending."""
    msgs = FakeMessageRepo(first_assistant=None)
    threads = FakeThreadRepo()
    bots = AsyncMock()
    bots.get = AsyncMock(return_value=_make_bot())

    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]
    svc._bots = bots

    # index 2 maps to alternate_greetings[1] = "Greetings, traveler."
    await svc.set_first_message(thread_id=5, bot_id=1, greeting_index=2)

    assert msgs.updates == []
    assert threads.pending == [(5, "Greetings, traveler.")]


@pytest.mark.asyncio
async def test_set_first_message_invalid_index_raises() -> None:
    """greeting_index out of range raises ValueError."""
    msgs = FakeMessageRepo(first_assistant=None)
    threads = FakeThreadRepo()
    bots = AsyncMock()
    bots.get = AsyncMock(return_value=_make_bot())

    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]
    svc._bots = bots

    with pytest.raises(ValueError, match="out of range"):
        await svc.set_first_message(thread_id=1, bot_id=1, greeting_index=99)


# ── get_stats ──────────────────────────────────────────────────────


class _FakeMessageRepoForStats:
    """In-memory ``MessageRepository`` stub for ``get_stats``.

    Records ``list_for_thread`` calls so tests can verify the service
    requests the full chain (not a paginated window). Returns whatever
    messages the test queues up, regardless of ``limit`` — the same
    contract as a real repo would honour for a thread with fewer rows
    than ``limit``.
    """

    def __init__(self, messages: list[MessageDTO]) -> None:
        self._messages = messages
        self.list_calls: list[tuple[int, int]] = []

    async def list_for_thread(
        self, thread_id: int, limit: int = 20, before_id: int | None = None
    ) -> list[MessageDTO]:
        self.list_calls.append((thread_id, limit))
        # Mirror the real SQL repo: filter out branch-inactive rows
        # just like the prod contract does, so test-side invariants
        # align with what the route returns.
        return [m for m in self._messages if before_id is None or (m.id or 0) < before_id]


class _FakeThreadRepoForStats:
    def __init__(self, exists: bool = True) -> None:
        self.exists = exists

    async def get(self, thread_id: int):
        return object() if self.exists else None

    async def set_pending_greeting(self, thread_id: int, content: str) -> None:  # pragma: no cover
        pass


@pytest.mark.asyncio
async def test_get_stats_counts_all_messages_and_estimates_tokens() -> None:
    """get_stats returns the full-message count (not the 50-page window)
    and a chars/4 token estimate that matches the frontend's proxy.
    """
    msgs = _FakeMessageRepoForStats(
        [
            MessageDTO(id=1, role="assistant", content="A" * 100),
            MessageDTO(id=2, role="user", content="B" * 80),
            MessageDTO(id=3, role="assistant", content="C" * 20),
        ]
    )
    threads = _FakeThreadRepoForStats(exists=True)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    stats = await svc.get_stats(thread_id=7)

    assert stats.thread_id == 7
    assert stats.message_count == 3
    assert stats.token_estimate == (100 + 80 + 20) // 4  # == 50
    # Service asked for a window larger than the 50-message UI default
    # so it sees past the first page.
    assert msgs.list_calls == [(7, 10_000)]


@pytest.mark.asyncio
async def test_get_stats_empty_thread_returns_zero() -> None:
    """An existing-but-empty thread returns a zero-count DTO, not an error.

    This is the case the chat header needs to render right after the
    user lands on a brand-new chat.
    """
    msgs = _FakeMessageRepoForStats([])
    threads = _FakeThreadRepoForStats(exists=True)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    stats = await svc.get_stats(thread_id=42)

    assert stats.thread_id == 42
    assert stats.message_count == 0
    assert stats.token_estimate == 0


@pytest.mark.asyncio
async def test_get_stats_missing_thread_raises_not_found() -> None:
    """A thread id that doesn't exist raises NotFoundError so the route
    layer can map it to 404 instead of returning phantom zeros.
    """
    msgs = _FakeMessageRepoForStats([])
    threads = _FakeThreadRepoForStats(exists=False)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    from app.application.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await svc.get_stats(thread_id=999)
