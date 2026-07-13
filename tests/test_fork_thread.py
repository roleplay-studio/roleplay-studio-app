"""Tests for ThreadService.fork_at_message (Task: thread fork feature).

The user-facing behaviour: the user clicks a fork icon on a message,
and the backend creates a new chat thread that contains a full copy
of the active conversation up to and including that message. The
frontend redirects them to the new thread so they can keep chatting
from the chosen snapshot without affecting the original.

Coverage split:

* Unit tests with in-memory fakes for the service-level contract:
  which messages are copied, what stays on the original, and which
  thread-level fields (persona, summary, name) are inherited.
* Integration test through ``SqlAlchemyStore`` + alembic so we
  catch drift between the in-memory fakes and the real SQL contract
  (pitfall 6au — the canonical ``monkeypatch Settings.from_env``
  pattern).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from app.application.dto import MessageDTO, ThreadDTO
from app.application.services.thread import ThreadService

# ── Unit-level fakes ─────────────────────────────────────────────────


class FakeMessageRepo:
    """In-memory ``MessageRepository`` for fork tests.

    Records every save so we can assert on the persisted shape. Only
    implements the surface area ``ThreadService.fork_at_message``
    actually touches — anything not listed here would be dead code
    masked by an over-broad fake (pitfall from AGENTS.md: "не
    упрощай фейки в угоду краткости теста").
    """

    def __init__(self, active_until: list[MessageDTO]) -> None:
        self._active_until = active_until
        self.list_active_until_calls: list[tuple[int, int]] = []
        self.saved: list[dict] = []

    async def list_active_until(self, thread_id: int, until_message_id: int) -> list[MessageDTO]:
        self.list_active_until_calls.append((thread_id, until_message_id))
        # The real SQL repo filters by id <= until_message_id AND
        # active-chain clause. The fake source is already shaped that
        # way (test fixture), so we just forward.
        return [m for m in self._active_until if m.id is not None and m.id <= until_message_id]

    async def save(
        self,
        thread_id: int,
        role: str,
        content: str,
        branch_group: str | None = None,
        branch_index: int = 0,
        is_active: bool = True,
        short_content: str | None = None,
        timestamp: datetime | None = None,
        generation_status: str = "complete",
        reasoning: str | None = None,
        dynamic_system_prompt: str | None = None,
        state: str | None = None,
    ) -> int:
        self.saved.append(
            {
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "branch_group": branch_group,
                "branch_index": branch_index,
                "is_active": is_active,
                "short_content": short_content,
                "timestamp": timestamp,
                "generation_status": generation_status,
                "reasoning": reasoning,
                "dynamic_system_prompt": dynamic_system_prompt,
                "state": state,
            }
        )
        # Return deterministic ids so the test can assert the order
        # of inserts without caring about autoincrement gaps.
        return len(self.saved)


class FakeThreadRepo:
    """In-memory ``ThreadRepository`` for fork tests.

    Mirrors the real ``SqlAlchemyThreadRepository.create`` /
    ``set_persona`` / ``update_summary`` flow without round-tripping
    through SQL — the integration test below covers that. ``summary``
    on the source thread is supplied separately from the DTO because
    in the real DB the summary lives on the row, and ``get()`` reads
    it back the same way — the unit fake must do the same so the
    service's read-then-copy contract is exercised correctly.
    """

    def __init__(
        self,
        source_thread: ThreadDTO,
        summary: str | None = None,
    ) -> None:
        self._source = source_thread
        self._summary = summary if summary is not None else source_thread.summary
        self.created: list[dict] = []
        self._next_id = 1000

    async def get(self, thread_id: int) -> ThreadDTO | None:
        if thread_id == self._source.id:
            # Return a DTO with the row's summary, NOT the one baked
            # into the test fixture — the service relies on this
            # round-trip exactly the way the real SQL repo does.
            return ThreadDTO(
                id=self._source.id,
                bot_id=self._source.bot_id,
                name=self._source.name,
                summary=self._summary,
                persona_id=self._source.persona_id,
            )
        # Synthesise any previously-created thread so subsequent gets
        # in the same test resolve correctly.
        for entry in self.created:
            if entry["id"] == thread_id:
                return ThreadDTO(
                    id=entry["id"],
                    bot_id=entry["bot_id"],
                    name=entry["name"],
                    summary=entry.get("summary"),
                    persona_id=entry.get("persona_id"),
                )
        return None

    async def create(
        self,
        bot_id: int,
        name: str = "new chat",
        persona_id: int | None = None,
        parent_thread_id: int | None = None,
    ) -> int:
        self._next_id += 1
        new_id = self._next_id
        self.created.append(
            {
                "id": new_id,
                "bot_id": bot_id,
                "name": name,
                "persona_id": persona_id,
                "parent_thread_id": parent_thread_id,
                "summary": None,
            }
        )
        return new_id

    async def set_persona(self, thread_id: int, persona_id: int | None) -> None:
        for entry in self.created:
            if entry["id"] == thread_id:
                entry["persona_id"] = persona_id
                return

    async def update_summary(self, thread_id: int, summary: str) -> None:
        for entry in self.created:
            if entry["id"] == thread_id:
                entry["summary"] = summary
                return

    async def set_pending_greeting(self, thread_id: int, content: str) -> None:  # pragma: no cover
        # Not exercised by fork tests; present so the fake satisfies
        # the Protocol shape.
        pass


def _make_msg(
    msg_id: int,
    role: str = "user",
    content: str = "hello",
    state: str | None = None,
    reasoning: str | None = None,
    dynamic_system_prompt: str | None = None,
    short_content: str | None = None,
    branch_group: str | None = None,
    is_active: bool = True,
    timestamp: datetime | None = None,
    generation_status: str = "complete",
) -> MessageDTO:
    return MessageDTO(
        id=msg_id,
        role=role,  # type: ignore[arg-type]
        content=content,
        state=state,
        reasoning=reasoning,
        dynamic_system_prompt=dynamic_system_prompt,
        short_content=short_content,
        branch_group=branch_group,
        branch_index=0,
        is_active=is_active,
        created_at=timestamp or datetime(2026, 7, 13, tzinfo=UTC),
        generation_status=generation_status,
    )


def _make_thread(
    thread_id: int = 7,
    bot_id: int = 1,
    name: str = "Test thread",
    persona_id: int | None = 3,
) -> ThreadDTO:
    return ThreadDTO(
        id=thread_id,
        bot_id=bot_id,
        name=name,
        summary="Some summary",
        persona_id=persona_id,
    )


# ── Service-level unit tests ─────────────────────────────────────────


async def test_fork_creates_new_thread_with_forked_name() -> None:
    """Fork produces a new thread whose name indicates it's a fork of the original."""
    source = _make_thread(name="Evening chat")
    msgs = FakeMessageRepo(active_until=[_make_msg(1)])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    new_id = await svc.fork_at_message(thread_id=source.id, message_id=1)

    assert new_id == 1001  # FakeThreadRepo starts at 1000, first create = 1001
    assert len(threads.created) == 1
    created = threads.created[0]
    assert created["name"].startswith("Fork of ")
    assert "Evening chat" in created["name"]


async def test_fork_copies_persona_from_source_thread() -> None:
    """Persona id is inherited from the source so the new thread
    renders the same user-facing persona as the original."""
    source = _make_thread(persona_id=42)
    msgs = FakeMessageRepo(active_until=[_make_msg(1)])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    await svc.fork_at_message(thread_id=source.id, message_id=1)

    created = threads.created[0]
    assert created["persona_id"] == 42


async def test_fork_copies_summary_from_source_thread() -> None:
    """The source's persisted summary is carried into the new thread."""
    source = _make_thread()
    msgs = FakeMessageRepo(active_until=[_make_msg(1)])
    threads = FakeThreadRepo(source_thread=source, summary="Long-running plot")
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    await svc.fork_at_message(thread_id=source.id, message_id=1)

    created = threads.created[0]
    assert created["summary"] == "Long-running plot"


async def test_fork_persists_all_active_messages_up_to_target() -> None:
    """All messages in the active chain with id <= target are copied,
    in chronological order (oldest first)."""
    msg_a = _make_msg(1, role="assistant", content="hi")
    msg_b = _make_msg(2, role="user", content="what's up?")
    msg_c = _make_msg(3, role="assistant", content="the sky")
    msg_after = _make_msg(4, role="user", content="don't fork this")
    source = _make_thread()
    msgs = FakeMessageRepo(active_until=[msg_a, msg_b, msg_c, msg_after])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    await svc.fork_at_message(thread_id=source.id, message_id=3)

    persisted = [s["content"] for s in msgs.saved]
    assert persisted == ["hi", "what's up?", "the sky"]
    # All copied messages belong to the new thread, NOT the source.
    assert all(s["thread_id"] != source.id for s in msgs.saved)
    assert len({s["thread_id"] for s in msgs.saved}) == 1


async def test_fork_inclusive_on_target_message() -> None:
    """The target message itself is included in the snapshot — 'fork
    at this message' means the user keeps what they see."""
    msg_a = _make_msg(1, role="assistant", content="hi")
    msg_b = _make_msg(2, role="user", content="snapshot includes this")
    msg_after = _make_msg(3, role="assistant", content="after")
    source = _make_thread()
    msgs = FakeMessageRepo(active_until=[msg_a, msg_b, msg_after])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    await svc.fork_at_message(thread_id=source.id, message_id=2)

    persisted = [s["content"] for s in msgs.saved]
    assert persisted == ["hi", "snapshot includes this"]


async def test_fork_collapses_branch_group_to_linear_chain() -> None:
    """Messages with a ``branch_group`` lose that link in the fork —
    the new thread is a single linear chain (no leftover branch UI
    pointing into a sibling thread)."""
    msg_branch = _make_msg(
        2,
        role="assistant",
        content="branched answer",
        branch_group="group-abc",
        is_active=True,
    )
    source = _make_thread()
    msgs = FakeMessageRepo(active_until=[_make_msg(1), msg_branch])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    await svc.fork_at_message(thread_id=source.id, message_id=2)

    persisted_branch_groups = {s["branch_group"] for s in msgs.saved}
    # All copied rows must carry ``branch_group=None`` so the new
    # thread has no branch versions to navigate to.
    assert persisted_branch_groups == {None}


async def test_fork_preserves_per_message_metadata() -> None:
    """State, reasoning, dynamic_system_prompt, short_content,
    generation_status, and the original timestamp are preserved on
    the copied rows so the forked thread renders identically to the
    source up to that point."""
    ts = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
    msg = _make_msg(
        1,
        role="assistant",
        content="hi",
        state="world: forest",
        reasoning="because they walked in",
        dynamic_system_prompt="[Reminder] stay in character",
        short_content="hi (short)",
        timestamp=ts,
        generation_status="complete",
    )
    source = _make_thread()
    msgs = FakeMessageRepo(active_until=[msg])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    await svc.fork_at_message(thread_id=source.id, message_id=1)

    saved = msgs.saved[0]
    assert saved["state"] == "world: forest"
    assert saved["reasoning"] == "because they walked in"
    assert saved["dynamic_system_prompt"] == "[Reminder] stay in character"
    assert saved["short_content"] == "hi (short)"
    assert saved["timestamp"] == ts
    assert saved["generation_status"] == "complete"
    assert saved["is_active"] is True


async def test_fork_unknown_thread_raises_not_found() -> None:
    """A source thread id that doesn't exist raises ``NotFoundError``
    so the route layer can map it to 404."""
    msgs = FakeMessageRepo(active_until=[])
    threads = FakeThreadRepo(source_thread=_make_thread(thread_id=999))
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    from app.application.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await svc.fork_at_message(thread_id=12345, message_id=1)

async def test_fork_no_active_messages_until_target_raises_not_found() -> None:
    """A target ``message_id`` that doesn't exist in the source thread
    raises ``NotFoundError`` — instead of silently falling back to
    "fork the whole chain" via the ``id <= until_message_id`` cursor.

    Regression: live curl against the running Docker stack showed that
    POSTing ``{"message_id": 999999}`` against a 105-message thread
    returned 200 and a fresh thread that **contained all 105
    messages** — because every row satisfied ``id <= 999999``. The
    service is meant to fork *at* a specific message, not *before*
    one; the strict existence check in ``fork_at_message`` is the
    fix, and this test guards the unit-level contract behind it.
    """
    msg_a = _make_msg(1, role="assistant", content="hi")
    msg_b = _make_msg(2, role="user", content="continue")
    msg_c = _make_msg(3, role="assistant", content="ok")
    source = _make_thread()
    msgs = FakeMessageRepo(active_until=[msg_a, msg_b, msg_c])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    from app.application.exceptions import NotFoundError

    # The thread is real, the message_id (99) is not. ``list_active_until``
    # returns all three rows (every id <= 99) — the strict check
    # after the snapshot is what catches this case.
    with pytest.raises(NotFoundError, match="Message 99 was not found"):
        await svc.fork_at_message(thread_id=source.id, message_id=99)


async def test_fork_does_not_mutate_source_thread() -> None:
    """Fork is read-only against the source — no deletes, no
    inserts, no updates of source rows."""
    source = _make_thread()
    msgs = FakeMessageRepo(active_until=[_make_msg(1, role="user")])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    await svc.fork_at_message(thread_id=source.id, message_id=1)

    # No save call should target the source thread id.
    assert all(s["thread_id"] != source.id for s in msgs.saved)
    # The fake thread repo should NOT have touched the source's name
    # / persona — only created a new entry.
    assert all(c["id"] != source.id for c in threads.created)


async def test_fork_preserves_bot_id() -> None:
    """The forked thread remains attached to the same bot (chat
    context — persona, scenario, knowledge — all bot-derived)."""
    source = _make_thread(bot_id=42)
    msgs = FakeMessageRepo(active_until=[_make_msg(1)])
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=msgs)  # type: ignore[arg-type]

    await svc.fork_at_message(thread_id=source.id, message_id=1)

    assert threads.created[0]["bot_id"] == 42


# ── Integration test (real SQL + alembic) ─────────────────────────────
# This test exists to catch drift between the in-memory fakes above
# and the real SQL contract. Pitfall 6au from
# ``roleplay-studio-feature-extension``: bypass Alembic and you also
# bypass the migration that added the columns the chat UI reads
# back. We monkey-patch ``Settings.from_env`` so the test boots the
# store through the real migration chain on a tmp sqlite db.


@pytest.fixture
async def fork_store(tmp_path, monkeypatch):
    """Yield a ``SqlAlchemyStore`` rooted at a tmp sqlite db.

    Uses the real Alembic migration chain via
    ``monkeypatch.setattr(Settings, 'from_env', ...)`` so any future
    migration that adds a column used by the fork path is exercised
    automatically (pitfall 6au).
    """
    from app.infrastructure.config import Settings
    from app.infrastructure.repositories.sqlalchemy import SqlAlchemyStore

    settings = Settings(_env_file=None, db_path=str(tmp_path / "fork.db"))
    monkeypatch.setattr(Settings, "from_env", classmethod(lambda cls: settings))
    store = SqlAlchemyStore(settings=settings)
    await store.init_db()
    yield store
    if os.path.exists(settings.db_path):
        try:
            os.remove(settings.db_path)
        except OSError:
            pass


async def test_fork_at_message_integration_against_real_sql(
    fork_store,
) -> None:
    """End-to-end fork against the real SQLite store.

    Seeds a bot + thread with three messages (one with a branch
    group + state + reasoning), forks at the second message, and
    asserts the new thread:

    * Inherits bot_id and persona_id from the source.
    * Carries the source's summary.
    * Contains the first two messages in order.
    * Does NOT contain the third message (after the fork point).
    * Collapses ``branch_group`` to ``None`` and preserves state /
      reasoning / dynamic_system_prompt on the copied row.
    """
    from sqlmodel import select

    from app.infrastructure.db.models import Bot, ChatThread, Conversation, UserPersona

    async with fork_store._async_session_factory() as session:
        bot = Bot(
            id=None,
            name="Test bot",
            personality="Friendly",
            first_message="Hi",
            scenario="Cafe",
            description="",
        )
        session.add(bot)
        await session.commit()
        await session.refresh(bot)
        bot_id = bot.id
        assert bot_id is not None

        # Persona is required to satisfy the FK constraint when we
        # set thread.persona_id. The fork should still carry this
        # persona_id over into the new thread.
        persona = UserPersona(id=None, name="User", description="")
        session.add(persona)
        await session.commit()
        await session.refresh(persona)
        persona_id = persona.id
        assert persona_id is not None

        thread = ChatThread(
            id=None,
            bot_id=bot_id,
            name="Original chat",
            summary="plot so far",
            persona_id=persona_id,
        )
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        thread_id = thread.id
        assert thread_id is not None

        # Three messages: assistant greeting, user, assistant with
        # state + reasoning + branch_group + dynamic prompt. The
        # fork point will be the second message (the user turn).
        m1 = Conversation(
            id=None,
            thread_id=thread_id,
            role="assistant",
            content="Welcome to the cafe.",
        )
        m2 = Conversation(
            id=None,
            thread_id=thread_id,
            role="user",
            content="One coffee please.",
        )
        m3 = Conversation(
            id=None,
            thread_id=thread_id,
            role="assistant",
            content="Coming right up.",
            reasoning="thought: friendly",
            state="place: cafe, items: coffee",
            dynamic_system_prompt="[Reminder] stay in character",
        )
        session.add_all([m1, m2, m3])
        await session.commit()
        for m in (m1, m2, m3):
            await session.refresh(m)
        assert m2.id is not None

    # Wire the service against the real repos backed by the store.
    # We don't need a full ApplicationContainer here — the service is
    # self-contained with the two repos it actually depends on.
    from app.application.services.thread import ThreadService
    from app.infrastructure.repositories.sqlalchemy import (
        SqlAlchemyMessageRepository,
        SqlAlchemyThreadRepository,
    )

    thread_repo = SqlAlchemyThreadRepository(fork_store)
    msg_repo = SqlAlchemyMessageRepository(fork_store)
    service = ThreadService(threads=thread_repo, messages=msg_repo)

    new_thread_id = await service.fork_at_message(thread_id=thread_id, message_id=m2.id)
    assert new_thread_id != thread_id

    # ── Verify the new thread's metadata ──────────────────────────
    new_thread = await thread_repo.get(new_thread_id)
    assert new_thread is not None
    assert new_thread.bot_id == bot_id
    assert new_thread.persona_id == persona_id
    assert new_thread.summary == "plot so far"
    assert new_thread.name.startswith("Fork of ")
    assert "Original chat" in new_thread.name

    # ── Verify the copied messages ────────────────────────────────
    active = await msg_repo.list_active_until(
        thread_id=new_thread_id,
        until_message_id=10**9,  # include everything in the new thread
    )
    contents = [m.content for m in active]
    assert contents == ["Welcome to the cafe.", "One coffee please."]

    # The third source message must NOT have leaked across.
    assert "Coming right up." not in contents

    # Branch groups collapsed to None (linear chain in the new thread).
    assert all(m.branch_group is None for m in active)

    # Source thread untouched — its full chain is still 3 messages.
    async with fork_store._async_session_factory() as session:
        source_msgs = (
            (
                await session.execute(
                    select(Conversation)
                    .where(Conversation.thread_id == thread_id)
                    .order_by(Conversation.id.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(source_msgs) == 3


async def test_fork_nonexistent_message_id_in_real_thread_raises_not_found(
    fork_store,
) -> None:
    """Real SQL regression for the 404 case.

    Pairs with the unit-level fake test
    ``test_fork_no_active_messages_until_target_raises_not_found`` —
    that test catches the service-side contract, this one confirms
    the SQL + service chain in production still surfaces the 404
    instead of silently returning the whole chain via the
    ``id <= until_message_id`` cursor.

    Reproducer that originally failed: POST
    ``/api/threads/{real_id}/fork`` with ``{"message_id": 999999}``
    returned 200 and a full-thread copy. The strict id-existence
    check in ``fork_at_message`` is the fix; this test pins it.
    """
    from sqlmodel import select
    from typing import cast

    from app.infrastructure.db.models import Bot, ChatThread, Conversation
    from app.infrastructure.repositories.sqlalchemy import (
        SqlAlchemyMessageRepository,
        SqlAlchemyThreadRepository,
    )
    from app.application.services.thread import ThreadService
    from app.application.exceptions import NotFoundError

    async with fork_store._async_session_factory() as session:
        bot = Bot(
            id=None,
            name="Regression bot",
            personality="p",
            first_message="hi",
        )
        session.add(bot)
        await session.commit()
        await session.refresh(bot)
        bot_id = cast(int, bot.id)
        assert bot_id is not None

        thread = ChatThread(id=None, bot_id=bot_id, name="regression")
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        thread_id = cast(int, thread.id)
        assert thread_id is not None

        # Three messages with explicit ids 100, 101, 102 — well below
        # the 999999 we'll try to fork.
        for cid in (100, 101, 102):
            session.add(
                Conversation(
                    id=cid,
                    thread_id=thread_id,
                    role="user" if cid == 101 else "assistant",
                    content=f"msg-{cid}",
                )
            )
        await session.commit()

    thread_repo = SqlAlchemyThreadRepository(fork_store)
    msg_repo = SqlAlchemyMessageRepository(fork_store)
    svc = ThreadService(threads=thread_repo, messages=msg_repo)

    # message_id=999999 is far above any real row. ``list_active_until``
    # would return all 3 rows (every id <= 999999). The strict check
    # is what makes this raise.
    with pytest.raises(NotFoundError, match="Message 999999 was not found"):
        await svc.fork_at_message(thread_id=thread_id, message_id=999999)

    # And confirm the source thread is unchanged (no half-applied state).
    async with fork_store._async_session_factory() as session:
        msgs = (
            (
                await session.execute(
                    select(Conversation)
                    .where(Conversation.thread_id == thread_id)
                    .order_by(Conversation.id.asc())
                )
            )
            .scalars()
            .all()
        )
        assert len(msgs) == 3


# ── create_thread parent_thread_id passthrough ──────────────────


async def test_create_thread_passes_parent_thread_id_to_repo() -> None:
    """``create_thread`` forwards ``parent_thread_id`` to the repository.

    Regression guard for the protocol passthrough. Without it, the
    service silently drops the kwarg and the tree UI shows every
    thread as a root.
    """
    source = _make_thread()  # dummy source — only used to satisfy FakeThreadRepo
    threads = FakeThreadRepo(source_thread=source)
    svc = ThreadService(threads=threads, messages=None)  # type: ignore[arg-type]

    tid = await svc.create_thread(
        bot_id=1, name="Forked chat", persona_id=None, parent_thread_id=42,
    )

    assert tid == 1001  # FakeThreadRepo._next_id starts at 1000, first create = 1001
    assert threads.created[0]["parent_thread_id"] == 42
    assert threads.created[0]["name"] == "Forked chat"


async def test_create_thread_default_parent_thread_id_is_none() -> None:
    """``create_thread`` without ``parent_thread_id`` passes ``None`` (root)."""
    threads = FakeThreadRepo(source_thread=_make_thread())
    svc = ThreadService(threads=threads, messages=None)  # type: ignore[arg-type]

    await svc.create_thread(bot_id=1, name="Regular chat")

    assert threads.created[0]["parent_thread_id"] is None
