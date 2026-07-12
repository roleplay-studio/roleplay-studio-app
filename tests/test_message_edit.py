"""Unit tests for message editing (branching + timestamp preservation).

Tests ThreadService.update_message() — the core logic that:
  - Creates branch groups on first edit
  - Preserves original message timestamp so edited messages stay in place
  - Supports multiple edits (versioning)
  - Handles empty content and missing messages
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.application.dto import MessageDTO
from app.application.exceptions import NotFoundError
from app.application.services import ThreadService

# ── Fake MessageRepository with branch + timestamp support ────────────


class EditFakeMessageRepo:
    """Message repository mock focused on edit/branch operations.

    Tracks messages with full DTO state so we can inspect timestamps,
    branch groups, and active/inactive flags after edits.
    """

    def __init__(self):
        self._msgs: list[MessageDTO] = []
        self._next_id = 1
        self._update_branch_calls: list[dict[str, Any]] = []

    async def save(
        self,
        thread_id,
        role,
        content,
        branch_group=None,
        branch_index=0,
        is_active=True,
        short_content=None,
        timestamp=None,
        generation_status: str = "complete",
        dynamic_system_prompt=None,
        state=None,
    ):
        mid = self._next_id
        self._next_id += 1
        msg = MessageDTO(
            id=mid,
            role=role,
            content=content,
            short_content=short_content,
            branch_group=branch_group,
            branch_index=branch_index,
            is_active=is_active,
            created_at=timestamp,
            versions=[],
            state=state,
        )
        self._msgs.append(msg)
        return mid

    async def save_branch(
        self,
        thread_id,
        role,
        content,
        branch_group,
        branch_index,
        timestamp=None,
        generation_status: str = "complete",
        state=None,
        # 0.0.6 — float prompt snapshot: signature kept aligned
        # with the real ``MessageRepository.save_branch``.
        dynamic_system_prompt: str | None = None,
    ):
        return await self.save(
            thread_id,
            role,
            content,
            branch_group=branch_group,
            branch_index=branch_index,
            is_active=True,
            timestamp=timestamp,
            state=state,
        )

    async def list_for_thread(self, thread_id, limit=200):
        # Return messages in chronological order (simulating DB sort)
        result = [
            m for m in self._msgs if m.id is not None and (m.branch_group is None or m.is_active)
        ]
        # Sort by (created_at, id) ascending to simulate real DB ordering
        result.sort(key=lambda m: (m.created_at or datetime.min, m.id or 0))
        return result[-limit:]

    async def get_versions(self, message_id):
        target = next((m for m in self._msgs if m.id == message_id), None)
        if target is None or target.branch_group is None:
            return []
        versions = sorted(
            [m for m in self._msgs if m.branch_group == target.branch_group],
            key=lambda m: m.branch_index,
        )
        return versions

    async def update_branch(self, message_id, branch_group, branch_index, is_active):
        self._update_branch_calls.append(
            {
                "message_id": message_id,
                "branch_group": branch_group,
                "branch_index": branch_index,
                "is_active": is_active,
            }
        )
        for msg in self._msgs:
            if msg.id == message_id:
                msg.branch_group = branch_group
                msg.branch_index = branch_index
                msg.is_active = is_active
                break

    async def update(self, message_id, content):
        pass

    async def delete(self, message_id):
        pass

    async def delete_from(self, thread_id, message_id):
        pass

    async def clear_thread(self, thread_id):
        pass

    async def save_exchange(self, thread_id, user_input, assistant_response):
        pass

    async def update_short_content(self, message_id, short_content):
        pass

    async def switch_version(self, branch_group, target_version_id):
        pass

    async def get_last_bot_message(self, thread_id):
        return None

    async def delete_after(self, thread_id, message_id):
        pass

    async def deactivate_branch_group(self, branch_group, thread_id):
        pass


# ── Fake ThreadRepository (minimal — needed by ThreadService) ────────


class EditFakeThreadRepo:
    def __init__(self):
        self.threads: dict[int, object] = {}

    async def create(self, bot_id, name="new chat"):
        from app.application.dto import ThreadDTO

        tid = 1
        self.threads[tid] = ThreadDTO(id=tid, bot_id=bot_id, name=name)
        return tid

    async def get(self, thread_id):
        return self.threads.get(thread_id)

    async def rename(self, thread_id, name):
        pass

    async def list_for_bot(self, bot_id):
        return []

    async def list_recent(self, limit=20, bot_id=None):
        return []

    async def delete(self, thread_id):
        pass

    async def set_persona(self, thread_id, persona_id):
        pass

    async def find_by_bot_and_persona(self, bot_id, persona_id):
        return None

    async def update_summary(self, thread_id, summary):
        pass


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def messages():
    return EditFakeMessageRepo()


@pytest.fixture
def service(messages):
    threads = EditFakeThreadRepo()
    return ThreadService(threads=threads, messages=messages)


@pytest.fixture
def now():
    return datetime.now(UTC)


# ── Helpers ───────────────────────────────────────────────────────────


async def seed_messages(
    repo: EditFakeMessageRepo,
    *,
    assistant_msgs: list[str],
    user_msgs: list[str] | None = None,
    start_time: datetime | None = None,
    thread_id: int = 1,
) -> list[MessageDTO]:
    """Seed a thread with alternating assistant/user messages.

    Returns the list of message DTOs in chronological order.
    Each message gets an incremental timestamp starting from start_time.
    """
    base_time = start_time or datetime.now(UTC)
    ids: list[int] = []

    for i, content in enumerate(assistant_msgs):
        ts = base_time + timedelta(seconds=i * 60)
        mid = await repo.save(thread_id, "assistant", content, timestamp=ts)
        ids.append(mid)

        if user_msgs and i < len(user_msgs):
            ts = base_time + timedelta(seconds=i * 60 + 30)
            await repo.save(thread_id, "user", user_msgs[i], timestamp=ts)

    return [m for m in repo._msgs if m.id in ids]


# ══════════════════════════════════════════════════════════════════════
#  update_message() — first edit
# ══════════════════════════════════════════════════════════════════════


class TestFirstEdit:
    async def test_creates_branch_group_and_preserves_timestamp(self, service, messages, now):
        """First edit: original marked inactive, new version keeps original timestamp."""
        ts1 = now
        ts2 = now + timedelta(seconds=30)
        ts3 = now + timedelta(seconds=60)
        await messages.save(1, "assistant", "Hello!", timestamp=ts1)
        await messages.save(1, "user", "Hi bot!", timestamp=ts2)
        await messages.save(1, "assistant", "How can I help?", timestamp=ts3)

        # Find the first assistant message
        all_msgs = await messages.list_for_thread(1)
        first_msg = all_msgs[0]
        assert first_msg.content == "Hello!"

        new_id = await service.update_message(1, first_msg.id, "Hey there!")

        assert new_id is not None
        all_msgs = await messages.list_for_thread(1)
        edited = next(m for m in all_msgs if m.id == new_id)
        assert edited.content == "Hey there!"
        assert edited.is_active is True
        assert edited.branch_group is not None

        # Timestamp preserved!
        assert edited.created_at == ts1

    async def test_original_becomes_inactive(self, service, messages, now):
        """Original message gets is_active=False after edit."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)
        await messages.save(1, "user", "Hi!", timestamp=ts + timedelta(seconds=30))

        all_msgs = await messages.list_for_thread(1)
        original = all_msgs[0]
        await service.update_message(1, original.id, "Hey!")

        # Original should be inactive now
        assert original.is_active is False
        assert original.branch_group is not None

    async def test_original_gets_branch_index_zero(self, service, messages, now):
        """Original message gets branch_index=0."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)
        await messages.save(1, "user", "Hi!", timestamp=ts + timedelta(seconds=30))

        all_msgs = await messages.list_for_thread(1)
        original = all_msgs[0]
        await service.update_message(1, original.id, "Hey!")

        assert original.branch_index == 0

    async def test_new_version_gets_branch_index_one(self, service, messages, now):
        """New edited version gets branch_index=1."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)
        await messages.save(1, "user", "Hi!", timestamp=ts + timedelta(seconds=30))

        all_msgs = await messages.list_for_thread(1)
        original = all_msgs[0]
        new_id = await service.update_message(1, original.id, "Hey!")

        all_msgs = await messages.list_for_thread(1)
        edited = next(m for m in all_msgs if m.id == new_id)
        assert edited.branch_index == 1

    async def test_edit_preserves_message_position_in_list(self, service, messages, now):
        """Edited message stays at the same chronological position."""
        ts1 = now
        ts2 = now + timedelta(seconds=30)
        ts3 = now + timedelta(seconds=60)
        await messages.save(1, "assistant", "Hello!", timestamp=ts1)
        await messages.save(1, "user", "Hi bot!", timestamp=ts2)
        await messages.save(1, "assistant", "How can I help?", timestamp=ts3)

        # Before edit: [Hello!, Hi bot!, How can I help?]
        before = await messages.list_for_thread(1)
        assert [m.content for m in before] == ["Hello!", "Hi bot!", "How can I help?"]

        first_msg = before[0]
        await service.update_message(1, first_msg.id, "Hey there!")

        # After edit: [Hey there!, Hi bot!, How can I help?]
        after = await messages.list_for_thread(1)
        assert len(after) == 3
        assert after[0].content == "Hey there!"
        assert after[0].id != first_msg.id  # new message id
        assert after[1].content == "Hi bot!"
        assert after[2].content == "How can I help?"

    async def test_preserves_position_when_editing_middle_message(self, service, messages, now):
        """Editing a message in the middle keeps it in the middle."""
        ts1 = now
        ts2 = now + timedelta(seconds=30)
        ts3 = now + timedelta(seconds=60)
        await messages.save(1, "assistant", "First", timestamp=ts1)
        await messages.save(1, "user", "Second", timestamp=ts2)
        await messages.save(1, "assistant", "Third", timestamp=ts3)

        before = await messages.list_for_thread(1)
        assert [m.content for m in before] == ["First", "Second", "Third"]

        # Edit the user message (middle)
        user_msg = before[1]
        assert user_msg.role == "user"

        await service.update_message(1, user_msg.id, "Edited second")

        after = await messages.list_for_thread(1)
        assert len(after) == 3
        assert after[0].content == "First"
        assert after[1].content == "Edited second"
        assert after[2].content == "Third"

    async def test_editing_last_message_stays_last(self, service, messages, now):
        """Editing the last message keeps it at the end."""
        ts1 = now
        ts2 = now + timedelta(seconds=30)
        ts3 = now + timedelta(seconds=60)
        await messages.save(1, "assistant", "First", timestamp=ts1)
        await messages.save(1, "user", "Second", timestamp=ts2)
        await messages.save(1, "assistant", "Third", timestamp=ts3)

        before = await messages.list_for_thread(1)
        last_msg = before[-1]
        assert last_msg.content == "Third"

        await service.update_message(1, last_msg.id, "Edited third")

        after = await messages.list_for_thread(1)
        assert len(after) == 3
        assert after[-1].content == "Edited third"


# ══════════════════════════════════════════════════════════════════════
#  update_message() — multiple edits
# ══════════════════════════════════════════════════════════════════════


class TestMultipleEdits:
    async def test_second_edit_adds_another_version(self, service, messages, now):
        """Editing an already-edited message adds another branch version."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)
        await messages.save(1, "user", "Hi!", timestamp=ts + timedelta(seconds=30))

        all_msgs = await messages.list_for_thread(1)
        first_msg = all_msgs[0]

        # First edit
        v1_id = await service.update_message(1, first_msg.id, "Hey!")
        assert v1_id is not None
        v1 = next(m for m in messages._msgs if m.id == v1_id)
        assert v1.branch_index == 1

        # Second edit (editing version 1)
        v2_id = await service.update_message(1, v1_id, "Yo!")
        assert v2_id is not None
        v2 = next(m for m in messages._msgs if m.id == v2_id)
        assert v2.branch_index == 2
        assert v2.content == "Yo!"
        assert v2.is_active is True

    async def test_timestamp_stays_same_across_multiple_edits(self, service, messages, now):
        """Timestamp is preserved across multiple edits."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)
        await messages.save(1, "user", "Hi!", timestamp=ts + timedelta(seconds=30))

        all_msgs = await messages.list_for_thread(1)
        first_msg = all_msgs[0]

        v1_id = await service.update_message(1, first_msg.id, "Hey!")
        v2_id = await service.update_message(1, v1_id, "Yo!")

        v2 = next(m for m in messages._msgs if m.id == v2_id)
        assert v2.created_at == ts

    async def test_only_latest_version_is_active(self, service, messages, now):
        """Only the most recent version in a branch group is active."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)
        await messages.save(1, "user", "Hi!", timestamp=ts + timedelta(seconds=30))

        all_msgs = await messages.list_for_thread(1)
        first_msg = all_msgs[0]

        v1_id = await service.update_message(1, first_msg.id, "Hey!")
        v2_id = await service.update_message(1, v1_id, "Yo!")

        # Only v2 should be active in the branch group
        all_versions = await messages.get_versions(v2_id)
        active_versions = [v for v in all_versions if v.is_active]
        assert len(active_versions) == 1
        assert active_versions[0].id == v2_id
        assert active_versions[0].content == "Yo!"

    async def test_multiple_edits_keep_same_position(self, service, messages, now):
        """Multiple edits still keep the message at the same position."""
        ts1 = now
        ts2 = now + timedelta(seconds=30)
        ts3 = now + timedelta(seconds=60)
        await messages.save(1, "assistant", "A", timestamp=ts1)
        await messages.save(1, "user", "B", timestamp=ts2)
        await messages.save(1, "assistant", "C", timestamp=ts3)

        all_msgs = await messages.list_for_thread(1)

        # Edit first message twice
        v1_id = await service.update_message(1, all_msgs[0].id, "A1")
        await service.update_message(1, v1_id, "A2")

        after = await messages.list_for_thread(1)
        assert len(after) == 3
        assert after[0].content == "A2"
        assert after[1].content == "B"
        assert after[2].content == "C"


# ══════════════════════════════════════════════════════════════════════
#  update_message() — edge cases
# ══════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    async def test_empty_content_returns_none(self, service, messages, now):
        """Empty or whitespace-only content returns None and does nothing."""
        await messages.save(1, "assistant", "Hello!", timestamp=now)
        all_msgs = await messages.list_for_thread(1)

        result = await service.update_message(1, all_msgs[0].id, "   ")
        assert result is None

        result = await service.update_message(1, all_msgs[0].id, "")
        assert result is None

        # Original should still be active (no changes)
        assert all_msgs[0].is_active is True
        assert all_msgs[0].branch_group is None

    async def test_nonexistent_message_raises_notfound(self, service):
        """Editing a message that doesn't exist raises NotFoundError."""
        with pytest.raises(NotFoundError):
            await service.update_message(1, 99999, "test")

    async def test_preserves_role(self, service, messages, now):
        """Edited message keeps the original role."""
        await messages.save(1, "assistant", "Hello!", timestamp=now)
        all_msgs = await messages.list_for_thread(1)

        new_id = await service.update_message(1, all_msgs[0].id, "Hey!")
        edited = next(m for m in messages._msgs if m.id == new_id)
        assert edited.role == "assistant"

        # Also test editing a user message
        await messages.save(1, "user", "Hi bot!", timestamp=now + timedelta(seconds=30))
        all_msgs = await messages.list_for_thread(1)
        user_msg = all_msgs[1]
        assert user_msg.role == "user"

        new_user_id = await service.update_message(1, user_msg.id, "Hello bot!")
        edited_user = next(m for m in messages._msgs if m.id == new_user_id)
        assert edited_user.role == "user"

    async def test_update_branch_called_with_correct_params(self, service, messages, now):
        """update_branch is called with the right parameters on first edit."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)

        all_msgs = await messages.list_for_thread(1)
        first_msg = all_msgs[0]

        await service.update_message(1, first_msg.id, "Hey!")

        assert len(messages._update_branch_calls) == 1
        call = messages._update_branch_calls[0]
        assert call["message_id"] == first_msg.id
        assert call["branch_index"] == 0
        assert call["is_active"] is False
        assert call["branch_group"] is not None

    async def test_new_id_is_different_from_original(self, service, messages, now):
        """Edited message gets a new ID."""
        await messages.save(1, "assistant", "Hello!", timestamp=now)
        all_msgs = await messages.list_for_thread(1)

        new_id = await service.update_message(1, all_msgs[0].id, "Hey!")
        assert new_id != all_msgs[0].id


# ══════════════════════════════════════════════════════════════════════
#  update_message() — with branch group already existing
# ══════════════════════════════════════════════════════════════════════


class TestExistingBranchGroup:
    async def test_edit_with_existing_branch_group_uses_it(self, service, messages, now):
        """Editing a message that already has a branch group reuses it."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)

        all_msgs = await messages.list_for_thread(1)
        first_msg = all_msgs[0]

        # First edit creates branch group
        v1_id = await service.update_message(1, first_msg.id, "Hey!")
        v1 = next(m for m in messages._msgs if m.id == v1_id)
        branch_group = v1.branch_group
        assert branch_group is not None

        # The original was marked — get_versions should now return all versions
        versions = await messages.get_versions(v1_id)
        assert len(versions) > 0

        # Second edit — should reuse the same branch_group
        v2_id = await service.update_message(1, v1_id, "Yo!")
        v2 = next(m for m in messages._msgs if m.id == v2_id)
        assert v2.branch_group == branch_group
        assert v2.branch_index == 2

        # get_versions should return all 3 versions (original, v1, v2)
        versions_after = await messages.get_versions(v2_id)
        assert len(versions_after) == 3

    async def test_get_versions_on_original_after_first_edit(self, service, messages, now):
        """After first edit, get_versions on original message ID returns versions."""
        ts = now
        await messages.save(1, "assistant", "Hello!", timestamp=ts)

        all_msgs = await messages.list_for_thread(1)
        first_msg = all_msgs[0]

        # First edit
        await service.update_message(1, first_msg.id, "Hey!")

        # Does get_versions work with the original (inactive) message?
        # The original now has branch_group, so get_versions should find it
        versions = await messages.get_versions(first_msg.id)
        assert len(versions) == 2  # original + v1
        assert versions[0].branch_index == 0  # original
        assert versions[1].branch_index == 1  # edited version

    async def test_edit_at_scale_preserves_all_positions(self, service, messages, now):
        """With many messages, editing any one preserves all positions."""
        base = now
        for i in range(6):
            ts = base + timedelta(minutes=i)
            await messages.save(1, "assistant" if i % 2 == 0 else "user", f"Msg {i}", timestamp=ts)

        before = await messages.list_for_thread(1)

        # Edit message at index 2 (assistant "Msg 2")
        target = before[2]
        v1_id = await service.update_message(1, target.id, "Msg 2 edited!")
        _ = await service.update_message(1, v1_id, "Msg 2 edited again!")

        after = await messages.list_for_thread(1)
        assert len(after) == 6
        assert after[0].content == "Msg 0"
        assert after[1].content == "Msg 1"
        assert after[2].content == "Msg 2 edited again!"
        assert after[3].content == "Msg 3"
        assert after[4].content == "Msg 4"
        assert after[5].content == "Msg 5"
