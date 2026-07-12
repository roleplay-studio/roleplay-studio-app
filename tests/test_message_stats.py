"""Integration tests for ``SqlAlchemyMessageRepository.count_active``.

Pinned via the same SqlAlchemyStore + tmp_path recipe as
``test_state_propagation.py`` so the SQL filter (``branch_group IS NULL
OR is_active``) is exercised against the real schema — not just a
fake. Catches a class of bugs where the count drifts from
``list_for_thread`` because the filter expressions diverge.
"""

from __future__ import annotations

import os

# The bot/thread repos import langchain transitively via the tests
# package — short-circuit heavyweight imports.
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


async def _seed_thread_with_messages(
    store, n_messages: int = 3
) -> tuple[int, int, list[int]]:
    """Create bot -> thread -> N user messages. Returns (bot_id, thread_id, [ids])."""
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(
        name="Test",
        personality="neutral",
        first_message="hello",
        bot_type="RolePlay",
    )
    thread_repo = SqlAlchemyThreadRepository(store)
    thread_id = await thread_repo.create(bot_id=bot_id, name="t")
    msgs_repo = SqlAlchemyMessageRepository(store)
    ids: list[int] = []
    for i in range(n_messages):
        mid = await msgs_repo.save(
            thread_id=thread_id,
            role="user" if i % 2 else "assistant",
            content=f"msg-{i}",
        )
        ids.append(mid)
    return bot_id, thread_id, ids


async def test_count_active_matches_list_for_thread_on_simple_chain(store):
    """count_active == len(list_for_thread) when there's no branching.

    This is the invariant the chat-header depends on. If the SQL filter
    drifts from the list query's filter, the header will silently show
    a different number than what the LLM sees.
    """
    _, thread_id, ids = await _seed_thread_with_messages(store, n_messages=4)

    msgs = SqlAlchemyMessageRepository(store)
    listed = await msgs.list_for_thread(thread_id, limit=10_000)
    count = await msgs.count_active(thread_id)

    assert count == len(listed)
    # The header is correct because both reads see the same chain.
    assert count == len(ids)


async def test_count_active_excludes_empty_content(store):
    """An empty-content row must not be counted.

    ``list_for_thread`` already drops empty rows when projecting to DTO;
    the count must agree so the header doesn't claim a message exists
    when the list shows one less.
    """
    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(
        name="t", personality="p", first_message="x", bot_type="RolePlay"
    )
    thread_repo = SqlAlchemyThreadRepository(store)
    thread_id = await thread_repo.create(bot_id=bot_id, name="t")
    msgs = SqlAlchemyMessageRepository(store)
    await msgs.save(thread_id, "user", "real message")
    # An empty / whitespace-only content should not appear in stats.
    await msgs.save(thread_id, "assistant", "")

    assert await msgs.count_active(thread_id) == 1


async def test_count_active_returns_zero_for_unknown_thread(store):
    """Unknown thread id returns 0 — not an exception.

    The service layer converts that to ``NotFoundError`` via the
    separate ``ThreadRepository.get`` check; the repo's job is just to
    be a quiet COUNT.
    """
    msgs = SqlAlchemyMessageRepository(store)
    assert await msgs.count_active(thread_id=9_999_999) == 0


async def test_count_active_only_active_branch_rows(store):
    """With branching, ``count_active`` counts only the active version
    per branch group (same filter ``list_for_thread`` applies).

    Setup:
      - 2 messages, no branch group
      - 2 more messages in branch group ``bg1``: v0 (inactive) + v1 (active)
      - 2 more in ``bg2``: v0 (inactive) + v2 (active)
    Expected active total = 2 + 1 + 1 = 4.
    """
    import uuid

    bot_repo = SqlAlchemyBotRepository(store)
    bot_id = await bot_repo.create(
        name="t", personality="p", first_message="x", bot_type="RolePlay"
    )
    thread_repo = SqlAlchemyThreadRepository(store)
    thread_id = await thread_repo.create(bot_id=bot_id, name="t")
    msgs = SqlAlchemyMessageRepository(store)

    await msgs.save(thread_id, "user", "old user 1")
    await msgs.save(thread_id, "assistant", "old assistant 1")
    # ``save_exchange`` is the orchestrator's breadcrumb; create the
    # branch pair directly via save() so we control is_active + bg.
    bg1 = str(uuid.uuid4())
    await msgs.save(
        thread_id,
        "assistant",
        "branch1-v0",
        branch_group=bg1,
        branch_index=0,
        is_active=False,
    )
    await msgs.save(
        thread_id,
        "assistant",
        "branch1-v1",
        branch_group=bg1,
        branch_index=1,
        is_active=True,
    )

    bg2 = str(uuid.uuid4())
    await msgs.save(
        thread_id,
        "user",
        "branch2-v0",
        branch_group=bg2,
        branch_index=0,
        is_active=False,
    )
    await msgs.save(
        thread_id,
        "user",
        "branch2-v2-active",
        branch_group=bg2,
        branch_index=2,
        is_active=True,
    )

    count = await msgs.count_active(thread_id)
    listed = await msgs.list_for_thread(thread_id, limit=10_000)

    assert count == 4
    # The list also resolves the branch filter the same way — the two
    # surfaces must agree or the header is wrong.
    assert count == len(listed)
