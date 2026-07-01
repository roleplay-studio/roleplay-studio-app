"""Tests for message pagination (before_id cursor).

Verifies that ThreadService.list_messages and the underlying
MessageRepository.list_for_thread support a `before_id` cursor so
long chats can be loaded in pages of `limit` messages from newest
to oldest, instead of being capped at a single hard limit.
"""

from __future__ import annotations

import pytest

from app.application.dto import MessageDTO
from app.application.services.thread import ThreadService


def _make_msg(msg_id: int, content: str = "x") -> MessageDTO:
    """Build a minimal MessageDTO for tests (id + content only)."""
    return MessageDTO(
        id=msg_id,
        role="user",
        content=content,
        short_content=None,
        created_at=None,
        branch_group=None,
        branch_index=0,
        is_active=True,
    )


class _StubMessageRepo:
    """Stub MessageRepository that records calls and returns canned data."""

    def __init__(self, pages: dict[int, list[MessageDTO]] | None = None) -> None:
        # pages: maps a synthetic cursor -> list of messages to return.
        # cursor 0 = "no cursor" (first page)
        self._pages = pages or {0: []}
        self.calls: list[dict] = []

    async def list_for_thread(
        self,
        thread_id: int,
        limit: int = 20,
        before_id: int | None = None,
    ) -> list[MessageDTO]:
        self.calls.append({"thread_id": thread_id, "limit": limit, "before_id": before_id})
        return list(self._pages.get(before_id or 0, []))


class _StubThreadRepo:
    def __init__(self) -> None:
        self.threads: dict[int, object] = {}


@pytest.fixture
def thread_service() -> ThreadService:
    return ThreadService(threads=_StubThreadRepo(), messages=_StubMessageRepo())  # type: ignore[arg-type]


# ── ThreadService.list_messages passes through before_id ───────────


@pytest.mark.asyncio
async def test_list_messages_passes_before_id_to_repository(
    thread_service: ThreadService,
) -> None:
    """Service must forward the before_id cursor to the repository."""
    msgs = thread_service._messages
    msgs._pages = {0: [_make_msg(101)], 50: [_make_msg(40)]}  # type: ignore[attr-defined]

    result = await thread_service.list_messages(thread_id=7, limit=50, before_id=50)

    assert [m.id for m in result] == [40]
    assert msgs.calls == [  # type: ignore[attr-defined]
        {"thread_id": 7, "limit": 50, "before_id": 50}
    ]


@pytest.mark.asyncio
async def test_list_messages_without_before_id_uses_none(
    thread_service: ThreadService,
) -> None:
    """Default behaviour (no cursor) must keep working."""
    msgs = thread_service._messages
    msgs._pages = {0: [_make_msg(101), _make_msg(100)]}  # type: ignore[attr-defined]

    result = await thread_service.list_messages(thread_id=7, limit=50)

    assert [m.id for m in result] == [101, 100]
    assert msgs.calls[-1]["before_id"] is None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_list_messages_default_limit_unchanged(
    thread_service: ThreadService,
) -> None:
    """Backward-compat: existing call sites with just thread_id must still work."""
    msgs = thread_service._messages
    msgs._pages = {0: []}  # type: ignore[attr-defined]

    await thread_service.list_messages(thread_id=7)

    assert msgs.calls[-1]["limit"] == 20  # type: ignore[attr-defined]
    assert msgs.calls[-1]["before_id"] is None  # type: ignore[attr-defined]
