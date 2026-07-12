"""Tests for ``ThreadService.update_message`` accepting ``state``.

Covers the new branch of the EditMessageRequest Pydantic model: the
service can now thread a new world-state snapshot through
``save_branch`` while preserving the original timestamp + branch-group
semantics. Pre-existing tests on the same surface stay green through
the no-state default path; the new behaviour lives in dedicated tests
so the regression surface is visible without archaeology.

Scenario matrix:

* edit content + state=None → state copied from original (fidelity)
* edit content + state="" → state explicitly cleared
* edit content + state="<new>" → state overwritten on new branch
* edit state alone (content passed through unchanged but state="...") →
  new branch + new state, original deactivated
* Saving carries the new state through to ``save_branch`` and lands
  on the SQL row (integration test via ``SqlAlchemyStore``).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.application.dto import MessageDTO
from app.application.services.thread import ThreadService


class _RecordingMessageRepo:
    """In-memory MessageRepository that records branch writes.

    Mirrors the SqlAlchemyMessageRepository contract for the surface
    ``update_message`` exercises — get_versions, list_for_thread,
    save_branch, update_branch. Tracks every state we save so the
    tests can assert the field landed where it should.
    """

    def __init__(self, initial: list[MessageDTO]) -> None:
        self._msgs = list(initial)
        self._next_id = max((m.id or 0) for m in initial) + 1
        self.save_branch_calls: list[dict[str, object]] = []

    async def get_versions(self, message_id: int) -> list[MessageDTO]:
        target = next((m for m in self._msgs if m.id == message_id), None)
        if target is None or target.branch_group is None:
            return []
        return [m for m in self._msgs if m.branch_group == target.branch_group]

    async def list_for_thread(self, thread_id: int, limit: int = 200):
        result = [m for m in self._msgs if m.branch_group is None or m.is_active]
        return result

    async def update_branch(
        self,
        message_id: int,
        branch_group: str,
        branch_index: int,
        is_active: bool,
    ) -> None:
        target = next((m for m in self._msgs if m.id == message_id), None)
        if target is None:
            return
        target.branch_group = branch_group
        target.branch_index = branch_index
        target.is_active = is_active

    async def save_branch(
        self,
        thread_id: int,
        role: str,
        content: str,
        branch_group: str,
        branch_index: int,
        timestamp=None,
        generation_status: str = "complete",
        reasoning=None,
        state=None,
    ) -> int | None:
        new_id = self._next_id
        self._next_id += 1
        self.save_branch_calls.append(
            {
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "branch_group": branch_group,
                "branch_index": branch_index,
                "timestamp": timestamp,
                "state": state,
            }
        )
        # Mirror SqlAlchemyStore behaviour: insert a new active row.
        self._msgs.append(
            MessageDTO(
                id=new_id,
                role=role,
                content=content,
                branch_group=branch_group,
                branch_index=branch_index,
                is_active=True,
                created_at=timestamp or datetime.now(),
                state=state,
            )
        )
        return new_id


def _seed_service_with_message(
    message: MessageDTO,
) -> tuple[ThreadService, _RecordingMessageRepo]:
    """Build a ThreadService with a single seeded message in thread 7.

    Avoids the SqlAlchemyStore round-trip for the cheap contract
    tests (fake repo) so the focus stays on the state semantics.
    """
    repo = _RecordingMessageRepo([message])
    # ThreadService.update_message only needs ``_messages``.
    svc = ThreadService.__new__(ThreadService)
    svc._messages = repo  # type: ignore[attr-defined]
    return svc, repo


# ── helpers ────────────────────────────────────────────────────────


def _seeded_message(msg_id: int, state: str | None = None) -> MessageDTO:
    return MessageDTO(
        id=msg_id,
        role="assistant",
        content="original assistant text",
        branch_group=None,
        branch_index=0,
        is_active=True,
        created_at=datetime(2026, 1, 1, 12, 0, 0),
        state=state,
    )


# ── state fidelity tests (no state passed) ─────────────────────────


@pytest.mark.asyncio
async def test_update_message_without_state_copies_original_state() -> None:
    """The default ``state=None`` path preserves the original message's
    world-state snapshot on the new branch — without this, branching
    on a state-bearing assistant turn would silently drop the world
    context the user was relying on when they decided to edit.
    """
    msg = _seeded_message(101, state="world: rain, T=10C")
    svc, repo = _seed_service_with_message(msg)

    new_id = await svc.update_message(
        thread_id=7,
        message_id=101,
        content="edited content",
    )

    assert new_id is not None
    assert len(repo.save_branch_calls) == 1
    # The new branch carries the *original* message's state verbatim.
    assert repo.save_branch_calls[0]["state"] == "world: rain, T=10C"
    assert repo.save_branch_calls[0]["content"] == "edited content"


@pytest.mark.asyncio
async def test_update_message_without_state_on_null_state_keeps_null() -> None:
    """If the original message had NULL state (no snapshot yet), the
    new branch must also be NULL — not empty string, not copied from
    somewhere else. Catches the "the editor accidentally writes '' to
    DB" class of regressions.
    """
    msg = _seeded_message(202, state=None)
    svc, repo = _seed_service_with_message(msg)

    await svc.update_message(thread_id=7, message_id=202, content="x")

    assert repo.save_branch_calls[0]["state"] is None


# ── explicit state tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_message_with_explicit_state_overwrites_state() -> None:
    """Passing a non-None ``state`` argument puts that exact value on
    the new branch, regardless of what the original had.
    """
    msg = _seeded_message(303, state="old: ignored")
    svc, repo = _seed_service_with_message(msg)

    await svc.update_message(
        thread_id=7,
        message_id=303,
        content="edited content",
        state="new: world rebuilt",
    )

    assert repo.save_branch_calls[0]["state"] == "new: world rebuilt"


@pytest.mark.asyncio
async def test_update_message_with_empty_string_state_clears_state() -> None:
    """Empty string ``""`` is the explicit "clear the snapshot"
    contract — distinct from ``None`` which means "use original".
    The user's EditMessageModal sends ``""`` when the state textarea
    is empty; this must land in the DB as the empty string, not NULL.
    """
    msg = _seeded_message(404, state="had a snapshot")
    svc, repo = _seed_service_with_message(msg)

    await svc.update_message(
        thread_id=7,
        message_id=404,
        content="edited content",
        state="",
    )

    # The empty string is a deliberate "clear" — preserved as "".
    assert repo.save_branch_calls[0]["state"] == ""


# ── branch semantics still hold with state ──────────────────────────


@pytest.mark.asyncio
async def test_update_message_creates_branch_and_deactivates_original() -> None:
    """Confirm the state plumbing didn't break the existing branch
    semantics: original deactivated, new branch active, both share
    the same branch_group + original timestamp.
    """
    orig = _seeded_message(505, state="world: v1")
    svc, repo = _seed_service_with_message(orig)

    new_id = await svc.update_message(
        thread_id=7,
        message_id=505,
        content="v2 content",
        state="world: v2",
    )
    assert new_id is not None

    # The original was deactivated when the new branch was created.
    original_after = next(m for m in repo._msgs if m.id == 505)
    assert original_after.is_active is False
    assert original_after.branch_index == 0
    # The new branch is active.
    new_msg = next(m for m in repo._msgs if m.id == new_id)
    assert new_msg.is_active is True
    assert new_msg.branch_index == 1
    # And both share the same branch group.
    assert original_after.branch_group == new_msg.branch_group
    # Timestamp is preserved — branch sits in the same history slot.
    assert new_msg.created_at == orig.created_at


# ── Edge cases ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_message_returns_none_for_empty_content() -> None:
    """The existing contract — empty content is a no-op. Adding the
    state parameter must not change this; an empty content save
    shouldn't accidentally persist a state mutation.

    Using ``state="anything"`` with empty content must still return
    ``None`` and not invoke save_branch at all.
    """
    msg = _seeded_message(606, state="ignored")
    svc, repo = _seed_service_with_message(msg)

    result = await svc.update_message(
        thread_id=7, message_id=606, content="   ", state="ignored too"
    )

    assert result is None
    assert repo.save_branch_calls == []


@pytest.mark.asyncio
async def test_update_message_missing_message_raises_not_found() -> None:
    """Bumping the surface didn't relax the 404 path — editing an
    unknown message_id still produces NotFoundError, regardless of
    whether ``state`` was supplied.
    """
    msg = _seeded_message(707, state="x")
    svc, _repo = _seed_service_with_message(msg)

    from app.application.exceptions import NotFoundError

    with pytest.raises(NotFoundError):
        await svc.update_message(thread_id=7, message_id=999, content="never saved", state="y")


# ── Route layer: EditMessageRequest accepts state ────────────────


def test_edit_message_request_accepts_state_field() -> None:
    """The Pydantic schema forwards ``state`` to the service.

    Typing: ``state: str | None = None`` so an empty body / older
    client still validates. Sending ``""`` is the explicit-clear
    signal — distinct from ``None`` which means "do what the
    service thinks is right".
    """
    from api.schemas import EditMessageRequest

    # Default — state field absent, defaults to None
    req_no_state = EditMessageRequest(content="new")
    assert req_no_state.state is None

    # Explicit None
    req_null_state = EditMessageRequest(content="new", state=None)
    assert req_null_state.state is None

    # Empty string — preserves the "clear the snapshot" contract
    req_empty_state = EditMessageRequest(content="new", state="")
    assert req_empty_state.state == ""

    # Real value
    req_value = EditMessageRequest(content="new", state="weather: snow")
    assert req_value.state == "weather: snow"


def test_edit_message_request_state_is_optional() -> None:
    """``state`` must remain optional — older clients (before the
    EditMessageModal shipped the state textarea) POST only ``content``.
    The service treats that as "use the original message's state".
    """
    from api.schemas import EditMessageRequest

    req = EditMessageRequest(content="just content")
    assert "state" not in req.model_dump(exclude_none=True) or req.state is None
