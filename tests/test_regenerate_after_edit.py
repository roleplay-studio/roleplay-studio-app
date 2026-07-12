"""Regression test for the bug Dima reported:

  "I edit a user message (a new branch is created in the DB).
   I click regenerate on the assistant message.
   The active user-branch is deleted, and a new message appears
   in its place."

Root cause:
  ``ChatService.regenerate_message`` used to call
  ``messages.delete_after(thread_id, target_id)`` to clean up the
  "tail" of the conversation. ``delete_after`` is implemented as a
  raw ``DELETE FROM conversations WHERE id > target_id`` — it cuts
  by row id. Once ``update_message`` exists, the chain order and
  the id order can diverge: editing a user message creates a NEW
  row with a HIGHER id, so the freshly-edited user message sits
  past ``target_id`` in id-ordering while still being BEFORE
  ``target_id`` in the active conversation chain. The naive delete
  wipes it along with the legitimate tail.

Fix:
  New ``ChatService._delete_active_chain_after`` helper does a
  chain-aware delete: it loads the active chain (filtered by
  ``is_active`` / ``branch_group IS NULL``), reverses to ASC,
  locates target, and deletes only the messages that follow target
  in the active chain. User messages that came in via an edit
  (new id, but earlier in the chain) are untouched.

These tests cover Dima's exact scenario (edit user → regenerate
assistant) plus a few neighbour cases to lock the contract in.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import create_engine as sa_create_engine

from app.application.services.chat import ChatService
from app.application.services.thread import ThreadService
from app.infrastructure.config import Settings
from app.infrastructure.db.models import Bot, ChatThread, SQLModel
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyMessageRepository,
    SqlAlchemyStore,
    SqlAlchemyThreadRepository,
)

# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
async def db_env(tmp_path):
    """Fresh SQLite store + repos for one test."""
    db = tmp_path / "edit_regen.db"
    settings = Settings(db_path=str(db), _env_file=None)
    store = SqlAlchemyStore(settings=settings)

    sync_engine = sa_create_engine("sqlite:///" + str(db), echo=False)
    SQLModel.metadata.create_all(sync_engine)
    sync_engine.dispose()

    async with store._async_session_factory() as s:
        bot = Bot(
            name="EditRegenBot",
            personality="Friendly catgirl.",
            scenario="",
            first_message="Welcome!",
        )
        s.add(bot)
        await s.commit()
        await s.refresh(bot)
        assert bot.id is not None
        thread = ChatThread(bot_id=bot.id, name="edit-regen")
        s.add(thread)
        await s.commit()
        await s.refresh(thread)
        assert thread.id is not None
        thread_id = thread.id
        bot_id = bot.id

    msgs = SqlAlchemyMessageRepository(store=store)
    threads = SqlAlchemyThreadRepository(store=store)
    chat = ChatService(
        bots=_BotRepoStub(bot_id),
        messages=msgs,
        knowledge=_KnowledgeStub(),
        orchestrator=_StubOrchestrator(["regenerated response"]),
    )
    thread_service = ThreadService(threads=threads, messages=msgs)

    yield {
        "store": store,
        "msgs": msgs,
        "threads": threads,
        "chat": chat,
        "thread_service": thread_service,
        "thread_id": thread_id,
        "bot_id": bot_id,
    }

    await store._async_engine.dispose()


class _BotRepoStub:
    """Minimal bot repo so we can run ``ChatService._build_request``."""

    def __init__(self, bot_id: int):
        self._bot_id = bot_id

    async def get(self, bot_id):
        from types import SimpleNamespace

        return SimpleNamespace(
            id=bot_id,
            name="EditRegenBot",
            personality="Friendly catgirl.",
            scenario="",
            first_message="Welcome!",
            bot_type=None,
        )


class _KnowledgeStub:
    async def search(self, *args, **kwargs):
        return []

    async def has_documents(self, *args, **kwargs):
        return False


class _StubOrchestrator:
    """Yields one chunk and finishes — enough to drive the regen path."""

    def __init__(self, contents: list[str]):
        self._contents = contents
        self.last_request: Any = None

    async def generate_stream(self, request):
        from app.infrastructure.llm import LLMChunk

        self.last_request = request
        for c in self._contents:
            yield LLMChunk(content=c, reasoning=None)


async def _drain_regen(chat: ChatService, thread_id: int, target_id: int, bot_id: int):
    """Drive ``regenerate_message`` to completion; return the events."""
    return [e async for e in chat.regenerate_message(thread_id, target_id, bot_id)]


def _ts(base_minutes: int):
    """Monotonically-increasing timestamps so the SQL sort by
    ``timestamp DESC, id DESC`` (and its ASC reverse) gives the same
    chain order as insertion order. Without this, ``datetime.now(UTC)``
    inside the same test produces tie-stamps that flip the order
    when one of the messages is later edited (the new id > A3)."""
    from datetime import UTC, datetime, timedelta

    return datetime(2026, 6, 13, 12, 0, 0, tzinfo=UTC) + timedelta(minutes=base_minutes)


# ── The bug Dima hit ─────────────────────────────────────────────────


class TestEditUserThenRegenerateAssistant:
    """Reproduces the exact Dima scenario: user message is in an
    active branch (post-edit). Regenerating an EARLIER assistant
    message must NOT wipe the edited user message.

    Pre-fix behaviour: the edited user message (high id) was deleted
    by the naive ``delete_after`` because its id was greater than
    the target assistant's id.
    """

    async def test_editing_user_then_regenerating_assistant_preserves_user(self, db_env):
        msgs = db_env["msgs"]
        thread_id = db_env["thread_id"]
        chat = db_env["chat"]
        bot_id = db_env["bot_id"]
        ts = db_env["thread_service"]

        # Seed: [A1, U1, A2, U2, A3] in chronological order
        _a1 = await msgs.save(thread_id, "assistant", "A1", timestamp=_ts(0))
        await msgs.save(thread_id, "user", "U1", timestamp=_ts(1))
        a2 = await msgs.save(thread_id, "assistant", "A2", timestamp=_ts(2))  # noqa: F841
        u2 = await msgs.save(thread_id, "user", "U2", timestamp=_ts(3))
        a3 = await msgs.save(thread_id, "assistant", "A3", timestamp=_ts(4))

        # Pre-edit: the active chain in id-order (ASC) is
        #   [A1(base), U1, A2(a2), U2(u2), A3(a3)]
        # which matches the chain order (good).

        # Edit U2 — this creates a new row with a HIGHER id.
        new_u2_id = await ts.update_message(thread_id, u2, "U2 EDITED")
        assert new_u2_id is not None
        assert new_u2_id > a3, (
            "precondition: edited user message must have a higher id "
            "than the assistant message we will regenerate — this is "
            "exactly what triggers the id-vs-chain ordering bug"
        )

        # Pre-regen: the active chain is
        #   [A1, U1, A2, U2'(new_u2_id, is_active=True), A3]
        # — note that U2' has id > A3 but is BEFORE A3 in chain order.
        pre = await msgs.list_for_thread(thread_id, limit=50)
        # ``list_for_thread`` returns ASC chain order (oldest first) —
        # the repo queries DESC and then ``reversed`` to walk the
        # chain naturally for callers. The pre-edit chain was
        # [A1, U1, A2, U2, A3]; after the edit U2 is replaced by
        # U2' (new id, is_active=True) so the chain becomes
        # [A1, U1, A2, U2', A3] — the position is the same.
        contents_pre = [m.content for m in pre]
        assert contents_pre == ["A1", "U1", "A2", "U2 EDITED", "A3"], (
            f"precondition failed: {contents_pre}"
        )

        # The bug: regenerate A3 (the last assistant) — under the
        # old ``delete_after(A3.id)`` it would wipe U2' because
        # U2'.id > A3.id. Under the new chain-aware delete, U2' is
        # preserved (it's the user input that the new A3' must
        # respond to).
        events = await _drain_regen(chat, thread_id, a3, bot_id)
        done = next(e for e in events if e.get("type") == "done")

        # The new assistant version is on disk.
        assert done["message"]["content"] == "regenerated response"

        # The edited user message is still there.
        post = await msgs.list_for_thread(thread_id, limit=50)
        # list_for_thread returns ASC chain order (oldest first).
        post_asc = [m for m in post if m.is_active]
        contents_post = [m.content for m in post_asc]
        assert "U2 EDITED" in contents_post, (
            f"BUG: edited user message disappeared after regen. "
            f"Active chain after regen: {contents_post}"
        )

        # The chain after regen is [A1, U1, A2, U2 EDITED, A3'(new)]
        # — U2 stays because it's the user input the new A3' answers.
        assert contents_post == ["A1", "U1", "A2", "U2 EDITED", "regenerated response"]

        # And the LLM actually saw U2 EDITED as user_input — that's
        # the whole point of preserving it.
        assert chat._orchestrator.last_request is not None
        assert chat._orchestrator.last_request.user_input == "U2 EDITED"

    async def test_regenerate_last_assistant_with_no_user_after_keeps_chain(self, db_env):
        """Sibling sanity check: when there is no user message after
        the target assistant, regenerate leaves the chain structurally
        unchanged (the new assistant version just replaces the old).
        """
        msgs = db_env["msgs"]
        thread_id = db_env["thread_id"]
        chat = db_env["chat"]
        bot_id = db_env["bot_id"]

        await msgs.save(thread_id, "assistant", "A1", timestamp=_ts(0))
        await msgs.save(thread_id, "user", "U1", timestamp=_ts(1))
        a2 = await msgs.save(thread_id, "assistant", "A2", timestamp=_ts(2))

        events = await _drain_regen(chat, thread_id, a2, bot_id)
        done = next(e for e in events if e.get("type") == "done")
        assert done["message"]["content"] == "regenerated response"

        post = await msgs.list_for_thread(thread_id, limit=50)
        post_asc = [m for m in post if m.is_active]
        assert [m.content for m in post_asc] == ["A1", "U1", "regenerated response"]


# ── Chain-aware delete: full scenarios ───────────────────────────────


class TestChainAwareDelete:
    """Lock down the chain-aware delete in a few more shapes that
    are easy to break but show up in real chats."""

    async def test_regenerate_middle_assistant_drops_only_tail(self, db_env):
        """When target is in the middle of the chain, only the
        messages AFTER it in the active chain are dropped — both
        the user input that fed the now-orphaned assistant, and the
        next assistant itself.
        """
        msgs = db_env["msgs"]
        thread_id = db_env["thread_id"]
        chat = db_env["chat"]
        bot_id = db_env["bot_id"]

        # [A1, U1, A2, U2, A3, U3, A4]
        a1 = await msgs.save(thread_id, "assistant", "A1", timestamp=_ts(0))  # noqa: F841
        u1 = await msgs.save(thread_id, "user", "U1", timestamp=_ts(1))  # noqa: F841
        a2 = await msgs.save(thread_id, "assistant", "A2", timestamp=_ts(2))
        await msgs.save(thread_id, "user", "U2", timestamp=_ts(3))
        await msgs.save(thread_id, "assistant", "A3", timestamp=_ts(4))
        await msgs.save(thread_id, "user", "U3", timestamp=_ts(5))
        await msgs.save(thread_id, "assistant", "A4", timestamp=_ts(6))

        # Regenerate A2 (the middle assistant). The new A2' is
        # meant to answer U1, so the rest of the chain is now
        # orphaned and must be removed.
        await _drain_regen(chat, thread_id, a2, bot_id)

        post = await msgs.list_for_thread(thread_id, limit=50)
        post_asc = [m for m in post if m.is_active]
        contents = [m.content for m in post_asc]
        assert contents == ["A1", "U1", "regenerated response"], (
            f"regenerating the middle assistant should leave only "
            f"A1, U1 and the new A2'; got {contents}"
        )

    async def test_regenerate_first_assistant_drops_everything_after(self, db_env):
        msgs = db_env["msgs"]
        thread_id = db_env["thread_id"]
        chat = db_env["chat"]
        bot_id = db_env["bot_id"]

        a1 = await msgs.save(thread_id, "assistant", "A1", timestamp=_ts(0))
        await msgs.save(thread_id, "user", "U1", timestamp=_ts(1))
        await msgs.save(thread_id, "assistant", "A2", timestamp=_ts(2))

        await _drain_regen(chat, thread_id, a1, bot_id)

        post = await msgs.list_for_thread(thread_id, limit=50)
        post_asc = [m for m in post if m.is_active]
        # A1 is now the inactive v0 of its branch_group; the new
        # A1' is the active v1. Both are still in the DB but only
        # the active one is in the active chain.
        assert [m.content for m in post_asc] == ["regenerated response"]

    async def test_edit_then_regenerate_preserves_predecessor_chain(self, db_env):
        """The strongest contract: edit U1, regenerate A2 (the
        assistant that originally answered U1) — U1' must stay
        because the new A2' is meant to answer U1'.
        """
        msgs = db_env["msgs"]
        thread_id = db_env["thread_id"]
        chat = db_env["chat"]
        bot_id = db_env["bot_id"]
        ts = db_env["thread_service"]

        await msgs.save(thread_id, "assistant", "A1", timestamp=_ts(0))
        u1 = await msgs.save(thread_id, "user", "U1", timestamp=_ts(1))
        a2 = await msgs.save(thread_id, "assistant", "A2", timestamp=_ts(2))
        await msgs.save(thread_id, "user", "U2", timestamp=_ts(3))
        await msgs.save(thread_id, "assistant", "A3", timestamp=_ts(4))

        # Edit U1.
        new_u1_id = await ts.update_message(thread_id, u1, "U1 EDITED")
        assert new_u1_id is not None
        # The new U1' has a higher id than A2 — that's the trigger
        # condition for the bug.
        assert new_u1_id > a2

        # Regenerate A2.
        await _drain_regen(chat, thread_id, a2, bot_id)

        post = await msgs.list_for_thread(thread_id, limit=50)
        post_asc = [m for m in post if m.is_active]
        contents = [m.content for m in post_asc]
        # The chain becomes: [A1, U1' (edited), A2' (regenerated)]
        # — U2 and A3 are dropped because the regenerated A2'
        # re-answers U1'.
        assert contents == ["A1", "U1 EDITED", "regenerated response"], (
            f"U1' was wiped by regenerate; got {contents}"
        )
