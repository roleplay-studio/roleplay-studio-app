"""Integration tests for thread-list enrichment: ``list_for_bot_with_preview``
and ``list_recent_with_previews``.

The frontend thread-list UI (ChatDrawer / RecentChats / Dashboard) needs
message counts, last-message preview text, and last-message timestamps
to render. Previously these required N+1 ``GET /api/threads/{id}/stats``
calls. The new repository methods populate the data via a single SQL
LEFT JOIN + LATERAL subquery, matching the contract documented in
``ThreadDTO`` / ``RecentThreadDTO``.

Why integration rather than fakes: the SQL projection is the entire
contract — silent column drops are exactly what fakes can hide. Use a
real ``SqlAlchemyStore`` against a tmp SQLite file so the SQL is
exercised end-to-end.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock

import pytest

sys.modules.setdefault("langgraph", MagicMock())
sys.modules.setdefault("langgraph.graph", MagicMock())
sys.modules.setdefault("langchain_openai", MagicMock())
sys.modules.setdefault("langchain_core", MagicMock())
sys.modules.setdefault("langchain_core.messages", MagicMock())
sys.modules.setdefault("langchain_community", MagicMock())
sys.modules.setdefault("langchain_chroma", MagicMock())

from app.infrastructure.config import Settings  # noqa: E402
from app.infrastructure.repositories.sqlalchemy import (  # noqa: E402
    SqlAlchemyBotRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyPersonaRepository,
    SqlAlchemyStore,
    SqlAlchemyThreadRepository,
)


@pytest.fixture
async def store(tmp_path, monkeypatch):
    settings = Settings(_env_file=None, db_path=str(tmp_path / "v.db"))
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    s = SqlAlchemyStore(settings=settings)
    await s.init_db()
    yield s
    if os.path.exists(settings.db_path):
        try:
            os.remove(settings.db_path)
        except OSError:
            pass


async def _seed_bot_and_messages(
    store,
    *,
    bot_name: str = "Test Bot",
    with_persona: bool = True,
    n_messages: int = 3,
    assistant_short_content: str | None = "short assistant reply",
):
    """Create a bot + persona + thread + ``n_messages`` interleaved
    user/assistant turns. Returns (bot_id, thread_id, persona_id_or_None)."""
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(
        name=bot_name,
        personality="p",
        first_message="hello",
    )
    persona_id: int | None = None
    if with_persona:
        persona_repo = SqlAlchemyPersonaRepository(store)
        persona_id = await persona_repo.create(
            name="Alice",
            description="curious",
            avatar_path="/static/avatars/alice.png",
        )
    thread_repo = SqlAlchemyThreadRepository(store)
    tid = await thread_repo.create(bot_id=bot_id, persona_id=persona_id, name="T")
    msg_repo = SqlAlchemyMessageRepository(store)
    last_assistant_mid: int | None = None
    for i in range(n_messages):
        await msg_repo.save(
            thread_id=tid,
            role="user",
            content=f"user turn {i}",
        )
        short = assistant_short_content if i == n_messages - 1 else None
        last_assistant_mid = await msg_repo.save(
            thread_id=tid,
            role="assistant",
            content=f"assistant turn {i}",
            short_content=short,
        )
    return bot_id, tid, persona_id, last_assistant_mid


async def test_list_for_bot_with_preview_returns_counts_and_last_message(
    store,
) -> None:
    bot_id, _, _, _ = await _seed_bot_and_messages(
        store, bot_name="Poppy", with_persona=True, n_messages=3
    )
    # 3 user/assistant pairs = 6 messages; assert 6 (not 5, not 7).
    repo = SqlAlchemyThreadRepository(store)
    rows = await repo.list_for_bot_with_preview(bot_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.message_count == 6
    # last message is the assistant's third turn -> short_content is the
    # summarizer-style short text set on the last assistant bubble.
    assert row.last_message_preview == "short assistant reply"
    assert row.last_message_role == "assistant"
    assert row.last_message_at is not None  # seed sets timestamps via default
    # persona join propagates avatar_path.
    assert row.persona_name == "Alice"
    assert row.persona_avatar_path == "/static/avatars/alice.png"


async def test_list_for_bot_with_preview_returns_zero_for_empty_thread(
    store,
) -> None:
    """A thread that has no messages yet — preview fields fall back to
    ``None``/0 instead of raising."""
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(name="EmptyBot", personality="p", first_message="hi")
    thread_repo = SqlAlchemyThreadRepository(store)
    tid = await thread_repo.create(bot_id=bot_id, name="empty")

    rows = await thread_repo.list_for_bot_with_preview(bot_id)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == tid
    assert row.message_count == 0
    assert row.last_message_at is None
    assert row.last_message_preview is None
    assert row.last_message_role is None


async def test_list_for_bot_with_preview_excludes_inactive_branch_messages(
    store,
) -> None:
    """``branch_group IS NULL OR is_active`` is the filter used by
    ``list_for_thread`` — the preview count must match the same
    predicate. Branch rows that were deactivated (is_active=False)
    must NOT inflate message_count, because they no longer belong to
    the active chain.
    """
    bot_id, tid, _, _ = await _seed_bot_and_messages(store, n_messages=2)
    # 2 user/assistant pairs = 4 base messages.
    msg_repo = SqlAlchemyMessageRepository(store)
    # Add a branch row that's marked is_active=False — should NOT count.
    await msg_repo.save(
        thread_id=tid,
        role="assistant",
        content="branch off",
        branch_group="bg-x",
        branch_index=1,
        is_active=False,
    )
    # Add another active branch row that DOES count.
    await msg_repo.save(
        thread_id=tid,
        role="user",
        content="active turn in branch",
        branch_group="bg-y",
        branch_index=1,
        is_active=True,
    )
    repo = SqlAlchemyThreadRepository(store)
    rows = await repo.list_for_bot_with_preview(bot_id)
    row = rows[0]
    # 4 base + 1 active branch = 5. The is_active=False row is excluded.
    assert row.message_count == 5


async def test_list_for_bot_with_preview_orders_newest_activity_first(
    store,
) -> None:
    """Threads with messages have non-NULL ``last_message_at``;
    message-less threads fall back to ``t.created_at``. Either way the
    SQL ordering should never return a thread with messages ranked
    AFTER a strictly older empty thread — i.e. the activity signal
    overrides plain creation order. This is the contract the chat
    sidebar depends on."""
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(name="B1", personality="p", first_message="hi")
    # Create the message-bearing thread FIRST so its created_at is
    # older; then create the empty one. A naive ORDER BY t.created_at
    # DESC would put the empty thread first, which we explicitly
    # reject — activity must beat recency of creation.
    repo = SqlAlchemyThreadRepository(store)
    tid_with = await repo.create(bot_id=bot_id, name="T1")
    tid_empty = await repo.create(bot_id=bot_id, name="T2")

    msg_repo = SqlAlchemyMessageRepository(store)
    await msg_repo.save(thread_id=tid_with, role="user", content="hi")
    await msg_repo.save(thread_id=tid_with, role="assistant", content="hello")

    rows = await repo.list_for_bot_with_preview(bot_id)
    assert len(rows) == 2

    by_id = {r.id: r for r in rows}
    assert by_id[tid_with].message_count == 2
    assert by_id[tid_empty].message_count == 0
    # Activity-bearing thread has a real last_message_at signal.
    assert by_id[tid_with].last_message_at is not None
    # Empty thread has no activity — last_message_at stays NULL.
    # The frontend falls back to t.created_at for ordering such rows.
    assert by_id[tid_empty].last_message_at is None


async def test_list_for_bot_with_preview_returns_empty_for_unknown_bot(
    store,
) -> None:
    repo = SqlAlchemyThreadRepository(store)
    rows = await repo.list_for_bot_with_preview(99999)
    assert rows == []


async def test_list_recent_with_previews_returns_counts_and_short_content(
    store,
) -> None:
    bot_id, _, _, _ = await _seed_bot_and_messages(store, bot_name="RecentBot")
    repo = SqlAlchemyThreadRepository(store)
    recent = await repo.list_recent_with_previews()
    assert len(recent) == 1
    item = recent[0]
    assert item.thread_id > 0
    assert item.bot_id == bot_id
    assert item.bot_name == "RecentBot"
    assert item.message_count == 6
    assert item.last_message_short_content == "short assistant reply"
    # short_content wins over preview fallback when set.
    assert item.last_message_preview == "short assistant reply"
    assert item.last_message_at is not None


async def test_list_recent_with_previews_paginates_with_before_thread_id(
    store,
) -> None:
    """Keyset pagination: second page must only return threads with id
    strictly smaller than ``before_thread_id``. Used by the frontend
    infinite-scroll sentinel when cross-bot list exceeds one page."""
    repo = SqlAlchemyThreadRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(name="B", personality="p", first_message="hi")
    # Create 3 threads; default sort is newest-first so the largest id
    # is the "newest" visible row in the first page.
    tids = []
    for i in range(3):
        t = await repo.create(bot_id=bot_id, name=f"t{i}")
        tids.append(t)
    # Page 1: limit=2 returns the 2 highest-id threads.
    page1 = await repo.list_recent_with_previews(limit=2)
    assert len(page1) == 2
    assert page1[0].thread_id > page1[1].thread_id
    # Page 2: fetch rows older than page1's last id.
    page2 = await repo.list_recent_with_previews(limit=2, before_thread_id=page1[-1].thread_id)
    assert len(page2) == 1
    assert page2[0].thread_id < page1[-1].thread_id
    # The full set of tids matches the union of pages.
    returned = {p.thread_id for p in page1} | {p.thread_id for p in page2}
    assert returned == set(tids)


async def test_list_recent_with_previews_falls_back_to_created_at(
    store,
) -> None:
    """Threads with no messages still show up in the recent list,
    sorted by their creation timestamp as a fallback."""
    repo = SqlAlchemyThreadRepository(store)
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(name="B", personality="p", first_message="hi")
    await repo.create(bot_id=bot_id, name="newer")

    recent = await repo.list_recent_with_previews()
    assert len(recent) == 1
    item = recent[0]
    assert item.message_count == 0
    assert item.last_message_at is not None  # falls back to t.created_at
    assert item.last_message_preview == ""
    assert item.last_message_short_content is None
