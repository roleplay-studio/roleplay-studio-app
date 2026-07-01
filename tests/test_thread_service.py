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
