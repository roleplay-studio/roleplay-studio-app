"""Regression test for ``ChatService.regenerate_message`` when the
target thread contains no user messages — i.e. the user is
regenerating the bot's *greeting* (the auto-saved ``first_message``)
before they have said anything.

The bug:
  ``regenerate_message`` builds a ``SendMessageCommand`` whose
  ``user_input`` field is the last user message's content, falling
  back to ``""`` when no user messages exist. ``SendMessageCommand``
  enforces ``min_length=1`` on ``user_input``, so the empty fallback
  raises ``pydantic.ValidationError`` mid-iteration. The exception
  propagates up through ``start_regenerate._drain`` and is sent to
  the SSE queue as a ``BaseException``; the route then yields a
  pydantic-flavoured ``{"type": "error", "detail": "1 validation
  error for SendMessageCommand..."}`` to the frontend.

The fix (in ``app/application/services/chat.py``) substitutes a
neutral placeholder (``"[continue the conversation]"``) for the empty
fallback so the validator passes and the LLM gets a sensible
"keep going from the existing history" signal instead of a fabricated
user turn.

These tests pin down both halves of the contract:
  1. ``regenerate_message`` does NOT raise when no user messages exist.
  2. The new branch is persisted on the original greeting.
  3. The placeholder string is what reaches the LLM (so we don't
     regress to ``""`` if someone re-introduces the empty fallback).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.application.dto import MessageDTO
from app.application.services.chat import ChatService
from app.infrastructure.llm import LLMChunk

# ── Fakes ─────────────────────────────────────────────────────────────


class _FakeBots:
    async def get(self, bot_id):
        # ``first_message`` is set so ``_build_request``'s "reconstruct
        # the opening turn locally" branch can fire (chat.py:877-878).
        return SimpleNamespace(
            id=bot_id,
            name="GreetingBot",
            personality="Friendly catgirl.",
            scenario="",
            first_message="Welcome! I'm a friendly bot.",
            bot_type=None,
        )


class _FakeKnowledge:
    async def search(self, bot_id, query, top_k):
        return []

    async def has_documents(self, bot_id):
        return False


class _FakeOrchestrator:
    """Stub that yields preset LLMChunk objects, and records the
    last ConversationRequest the chat service built — so the test
    can assert that the ``user_input`` field is the placeholder,
    not an empty string."""

    def __init__(self, contents: list[str]):
        self._chunks = contents
        self.last_request: Any = None

    async def generate_stream(self, request):
        self.last_request = request
        for content in self._chunks:
            yield LLMChunk(content=content, reasoning=None)


class _FakeMessages:
    """Minimal in-memory message repository for this test.

    Only the methods ``regenerate_message`` actually touches are
    implemented — anything else raises ``NotImplementedError`` so
    the test fails fast if the production code path grows new
    dependencies.
    """

    def __init__(self) -> None:
        # Ordered list of (thread_id, MessageDTO) entries.
        self._store: list[tuple[int, MessageDTO]] = []
        self.deleted_after: list[tuple[int, int]] = []
        self.deactivated_groups: list[tuple[str, int]] = []
        self._next_id = 1

    async def save(self, thread_id, role, content, **kwargs) -> int:
        mid = self._next_id
        self._next_id += 1
        self._store.append(
            (
                thread_id,
                MessageDTO(
                    id=mid,
                    role=role,
                    content=content,
                    reasoning=kwargs.get("reasoning"),
                    branch_group=kwargs.get("branch_group"),
                    branch_index=kwargs.get("branch_index", 0),
                    is_active=kwargs.get("is_active", True),
                ),
            )
        )
        return mid

    async def list_for_thread(self, thread_id, limit=200, before_id=None):
        # Match the real SQL contract: ASC chain order (oldest first).
        # The real ``SqlAlchemyMessageRepository.list_for_thread`` issues
        # ``ORDER BY timestamp DESC, id DESC`` and then does
        # ``reversed(messages)`` so callers walk the chain naturally
        # (oldest → newest). The fakes have no real timestamps, so we
        # sort by id ASC, which is the only stable insertion order the
        # in-memory store tracks.
        result = [m for _, m in self._store if m.is_active]
        result.sort(key=lambda m: m.id or 0)
        return result[:limit]

    async def get_versions(self, message_id):
        target = next((m for _, m in self._store if m.id == message_id), None)
        if target is None or target.branch_group is None:
            return [target] if target else []
        return [m for _, m in self._store if m.branch_group == target.branch_group]

    async def update_branch(self, message_id, branch_group, branch_index, is_active):
        for i, (_, m) in enumerate(self._store):
            if m.id == message_id:
                self._store[i] = (
                    self._store[i][0],
                    MessageDTO(
                        id=m.id,
                        role=m.role,
                        content=m.content,
                        branch_group=branch_group,
                        branch_index=branch_index,
                        is_active=is_active,
                    ),
                )
                return

    async def delete(self, message_id):
        """Hard-delete a single row by id. Used by the chain-aware
        delete helper in ``ChatService``."""
        self._store = [(t, m) for (t, m) in self._store if m.id != message_id]

    async def delete_after(self, thread_id, message_id):
        self.deleted_after.append((thread_id, message_id))

    async def deactivate_branch_group(self, branch_group, thread_id):
        self.deactivated_groups.append((branch_group, thread_id))

    async def save_branch(
        self,
        thread_id,
        role,
        content,
        branch_group,
        branch_index,
        timestamp=None,
        generation_status="complete",
        reasoning: str | None = None,
        # 0.0.6 — float prompt snapshot, signature aligned with
        # the real ``MessageRepository.save_branch``.
        dynamic_system_prompt: str | None = None,
    ):
        return await self.save(
            thread_id,
            role,
            content,
            branch_group=branch_group,
            branch_index=branch_index,
            is_active=True,
            reasoning=reasoning,
        )

    # Everything else — never called by regenerate_message.
    async def get_last_bot_message(self, *args, **kwargs):
        return None

    async def clear_thread(self, *args, **kwargs):
        pass

    async def save_exchange(self, *args, **kwargs):
        pass

    async def save_first_assistant_if_absent(self, *args, **kwargs):
        return False

    async def update_short_content(self, *args, **kwargs):
        pass

    async def switch_version(self, *args, **kwargs):
        pass


def _make_service(messages, orch) -> ChatService:
    return ChatService(
        bots=_FakeBots(),
        messages=messages,
        knowledge=_FakeKnowledge(),
        orchestrator=orch,
    )


# ── The regression ────────────────────────────────────────────────────


class TestRegenerateGreeting:
    """Regenerate the bot's first_message in a fresh thread where
    the user has not spoken yet. Used to crash with
    ``pydantic.ValidationError: user_input String should have at
    least 1 character`` because the code substituted ``""`` for
    the missing last-user-message content."""

    @pytest.mark.asyncio
    async def test_does_not_raise_when_no_user_messages_exist(self):
        msgs = _FakeMessages()
        orch = _FakeOrchestrator(contents=["Greetings, traveller!"])
        # Seed a thread with just the bot's greeting (no user input).
        greeting_id = await msgs.save(1, "assistant", "Welcome! I'm a friendly bot.")

        service = _make_service(msgs, orch)

        # Before the fix: this raised pydantic.ValidationError and
        # the SSE consumer saw a verbose error payload.
        events = [
            event
            async for event in service.regenerate_message(
                thread_id=1, message_id=greeting_id, bot_id=1
            )
        ]

        # No error event — the stream completed normally.
        assert not any(e.get("type") == "error" for e in events), (
            f"regenerate_message emitted an error event when no user messages exist: {events}"
        )
        # The standard success events fire.
        assert any(e.get("type") == "meta" for e in events)
        assert any(e.get("type") == "done" for e in events)

    @pytest.mark.asyncio
    async def test_persists_new_branch_version(self):
        msgs = _FakeMessages()
        orch = _FakeOrchestrator(contents=["Greetings, traveller!"])
        greeting_id = await msgs.save(1, "assistant", "Welcome! I'm a friendly bot.")

        service = _make_service(msgs, orch)
        events = [
            event
            async for event in service.regenerate_message(
                thread_id=1, message_id=greeting_id, bot_id=1
            )
        ]
        done = next(e for e in events if e.get("type") == "done")

        # The new branch content matches what the orchestrator emitted.
        assert done["message"]["content"] == "Greetings, traveller!"
        # branch_index=1 because the original is now the inactive v0.
        assert done["message"]["branch_index"] == 1
        # Two versions total: the original (inactive) + the new one.
        assert len(done["versions"]) == 2

    @pytest.mark.asyncio
    async def test_placeholder_user_input_reaches_llm(self):
        """The fallback string is what flows into the orchestrator's
        ConversationRequest — never an empty string. This guards
        against a regression where someone re-introduces ``""``
        as the fallback and trips the pydantic validator.
        """
        msgs = _FakeMessages()
        orch = _FakeOrchestrator(contents=["A new greeting."])
        greeting_id = await msgs.save(1, "assistant", "Original greeting.")

        service = _make_service(msgs, orch)
        [
            event
            async for event in service.regenerate_message(
                thread_id=1, message_id=greeting_id, bot_id=1
            )
        ]

        # The orchestrator received the rebuilt request.
        assert orch.last_request is not None
        user_input = orch.last_request.user_input
        assert user_input, "user_input must not be empty"
        # Specific placeholder — matches the production code. If
        # the placeholder is changed, update both the test and the
        # service together.
        assert user_input == "[continue the conversation]"

    @pytest.mark.asyncio
    async def test_with_real_user_message_uses_user_content(self):
        """Defensive: when the thread DOES have a user message, the
        service must pass that real content (not the placeholder)
        into the LLM. The placeholder is a fallback, not a default.
        """
        msgs = _FakeMessages()
        orch = _FakeOrchestrator(contents=["Reply."])
        await msgs.save(1, "assistant", "Hi from bot.")
        await msgs.save(1, "user", "Hello, bot!")
        await msgs.save(1, "assistant", "Hi back!")

        service = _make_service(msgs, orch)
        [event async for event in service.regenerate_message(thread_id=1, message_id=3, bot_id=1)]

        assert orch.last_request is not None
        assert orch.last_request.user_input == "Hello, bot!", (
            "with a real user message in history, the LLM must get "
            "that real content — not the placeholder"
        )
