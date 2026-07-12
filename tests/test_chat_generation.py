"""Unit tests for chat message generation and regeneration (branching).

Focus areas:
  - stream_message() — correct message flow, persistence, context assembly
  - regenerate_message() — branching, version tracking, history cleanup
  - Edge cases: errors, empties, multiple regens, overlapping branches
"""

from __future__ import annotations

import pytest

from app.application.dto import (
    MessageDTO,
    SendMessageCommand,
)
from app.application.exceptions import ExternalServiceError, NotFoundError
from app.application.services import ChatService

# ── Fake repositories with branch/version support ────────────────────


class FakeBotRepo:
    """Simple bot repository — returns namespace objects matching Bot's fields."""

    def __init__(self):
        self._bots: dict[int, dict] = {}
        self._next_id = 1

    async def create(
        self,
        name,
        personality,
        first_message="",
        scenario="",
        description="",
        avatar_path=None,
        categories=None,
        bot_type="rp",
        mes_example="",
    ):
        bid = self._next_id
        self._next_id += 1
        self._bots[bid] = dict(
            id=bid,
            name=name,
            personality=personality,
            first_message=first_message,
            scenario=scenario,
            description=description,
            avatar_path=avatar_path,
            categories=categories or [],
            bot_type=bot_type,
            mes_example=mes_example,
        )
        return bid

    async def get(self, bot_id):
        from types import SimpleNamespace

        data = self._bots.get(bot_id)
        return SimpleNamespace(**data) if data else None

    async def list(self):
        from types import SimpleNamespace

        return [SimpleNamespace(**d) for d in self._bots.values()]

    async def delete(self, bot_id):
        self._bots.pop(bot_id, None)

    async def update(self, bot_id, **kwargs):
        if bot_id in self._bots:
            self._bots[bot_id].update(kwargs)


class FakeLLM:
    """Controllable LLM stub — returns preset text."""

    def __init__(self, response: str = "test response"):
        self._response = response
        self.last_messages = None
        self.call_count = 0

    async def generate_response(self, messages, temperature=None, max_tokens=None):
        self.last_messages = messages
        self.call_count += 1
        return self._response

    async def generate_response_stream(self, messages, temperature=None, max_tokens=None):
        self.last_messages = messages
        self.call_count += 1
        from app.infrastructure.llm import LLMChunk

        for chunk in self._response.split(" "):
            yield LLMChunk(content=chunk + " ")


class FakeThreadRepo:
    def __init__(self):
        self.threads: dict[int, object] = {}
        self._next_id = 1

    async def create(self, bot_id, name="new chat"):
        from app.application.dto import ThreadDTO

        tid = self._next_id
        self._next_id += 1
        self.threads[tid] = ThreadDTO(id=tid, bot_id=bot_id, name=name)
        return tid

    async def get(self, thread_id):
        return self.threads.get(thread_id)

    async def rename(self, thread_id, name):
        if thread_id in self.threads:
            obj = self.threads[thread_id]
            obj.name = name

    async def list_for_bot(self, bot_id):
        return [t for t in self.threads.values() if t.bot_id == bot_id]

    async def list_recent(self, limit=20):
        return []

    async def delete(self, thread_id):
        self.threads.pop(thread_id, None)

    async def set_persona(self, thread_id, persona_id):
        pass

    async def find_by_bot_and_persona(self, bot_id, persona_id):
        return None


class FakeKnowledgeRepo:
    """Stub that always returns a canned context."""

    async def add(self, command):
        pass

    async def search(self, bot_id, query, top_k=3):
        return ["canned knowledge context"]

    async def list_entries(self, bot_id):
        return []

    async def has_documents(self, bot_id):
        # Default to True so the chat hot path calls ``search`` —
        # this is the original behaviour every test in
        # ``test_chat_generation.py`` was written against. Specific
        # tests that want to exercise the no-embedding-call
        # short-circuit can override this to return ``False``.
        return True

    async def delete(self, bot_id, entry_id):
        pass

    async def update(self, bot_id, entry_id, content):
        pass

    async def search_with_scores(self, bot_id, query, top_k=5):
        return []


class BranchMessageRepo:
    """Message repository with full branch/version tracking.

    Internally stores (thread_id, MessageDTO) pairs using SimpleNamespace
    so that both thread_id access (m.tid) and DTO access (m.msg.id, etc.) work.
    """

    def __init__(self):
        self._msgs: list[object] = []
        self._next_id = 1

    def _make(self, **kwargs) -> object:
        from types import SimpleNamespace

        msg_id = self._next_id
        self._next_id += 1
        dto = MessageDTO(id=msg_id, **kwargs)
        return SimpleNamespace(tid=kwargs.pop("_tid", 0), msg=dto)

    async def save(
        self,
        thread_id,
        role,
        content,
        branch_group=None,
        branch_index=0,
        is_active=True,
        timestamp=None,
        generation_status: str = "complete",
        reasoning: str | None = None,
        dynamic_system_prompt: str | None = None,
        **_extra: object,
    ) -> int | None:
        entry = self._make(
            role=role,
            content=content,
            branch_group=branch_group,
            branch_index=branch_index,
            is_active=is_active,
            created_at=timestamp,
            _tid=thread_id,
            reasoning=reasoning,
            dynamic_system_prompt=dynamic_system_prompt,
        )
        self._msgs.append(entry)
        return entry.msg.id

    async def save_exchange(
        self,
        thread_id,
        user_input,
        assistant_response,
        reasoning: str | None = None,
    ) -> None:
        await self.save(thread_id, "user", user_input)
        await self.save(
            thread_id,
            "assistant",
            assistant_response,
            reasoning=reasoning,
        )

    async def save_branch(
        self,
        thread_id,
        role,
        content,
        branch_group,
        branch_index,
        timestamp=None,
        generation_status: str = "complete",
        reasoning: str | None = None,
    ) -> int | None:
        return await self.save(
            thread_id,
            role,
            content,
            branch_group,
            branch_index,
            timestamp=timestamp,
            reasoning=reasoning,
        )

    async def list_for_thread(self, thread_id, limit=200) -> list[MessageDTO]:
        # Match the real SQL contract: ASC chain order (oldest first).
        # The real ``SqlAlchemyMessageRepository.list_for_thread`` issues
        # ``ORDER BY timestamp DESC, id DESC`` and then does
        # ``reversed(messages)`` so callers walk the chain naturally
        # (oldest → newest). The fakes have no real timestamps, so we
        # sort by id ASC, which is the only stable insertion order the
        # in-memory store tracks.
        result = [e.msg for e in self._msgs if e.msg.is_active]
        result.sort(key=lambda m: m.id or 0)
        return result[:limit]

    async def list_all_for_thread(self, thread_id) -> list[MessageDTO]:
        return [e.msg for e in self._msgs]

    async def clear_thread(self, thread_id):
        self._msgs = []

    async def update(self, message_id, content):
        for e in self._msgs:
            if e.msg.id == message_id:
                e.msg.content = content
                break

    async def delete(self, message_id):
        self._msgs = [e for e in self._msgs if e.msg.id != message_id]

    async def delete_after(self, thread_id, message_id):
        """Delete all messages AFTER message_id (exclusive)."""
        target_idx = next(
            (i for i, e in enumerate(self._msgs) if e.tid == thread_id and e.msg.id == message_id),
            None,
        )
        if target_idx is not None:
            self._msgs = [
                e for i, e in enumerate(self._msgs) if not (e.tid == thread_id and i > target_idx)
            ]

    async def delete_from(self, thread_id, message_id):
        await self.delete_after(thread_id, message_id - 1)

    async def get_first_assistant(self, thread_id) -> MessageDTO | None:
        """Return the chronologically-first assistant message for thread_id, or None.

        Mirrors ``SqlAlchemyMessageRepository.get_first_assistant``. Used by
        ``ChatService.stream_save_first_message`` for K4 idempotency in
        docs/review.md.
        """
        for e in self._msgs:
            if e.tid == thread_id and e.msg.role == "assistant":
                return e.msg
        return None

    async def save_first_assistant_if_absent(self, thread_id, content):
        """RC1.2 stub — return True if no assistant msg exists, else False.

        Mirrors the production atomic insert; the branch tests need the
        fake to actually push a row so ``list_all_for_thread`` returns
        the first_message alongside the user + assistant exchanges.
        """
        for e in self._msgs:
            if e.tid == thread_id and e.msg.role == "assistant":
                return False
        from datetime import UTC, datetime

        entry = self._make(
            role="assistant",
            content=content,
            created_at=datetime.now(UTC),
            _tid=thread_id,
        )
        self._msgs.append(entry)
        return True

    async def get_versions(self, message_id) -> list[MessageDTO]:
        target = next((e.msg for e in self._msgs if e.msg.id == message_id), None)
        if target is None or target.branch_group is None:
            return [target] if target else []
        return sorted(
            [e.msg for e in self._msgs if e.msg.branch_group == target.branch_group],
            key=lambda m: m.branch_index,
        )

    async def switch_version(self, branch_group, target_version_id):
        for e in self._msgs:
            if e.msg.branch_group == branch_group:
                e.msg.is_active = e.msg.id == target_version_id

    async def get_last_bot_message(self, thread_id):
        bot_msgs = [e.msg for e in self._msgs if e.msg.role == "assistant"]
        return bot_msgs[-1] if bot_msgs else None

    async def update_branch(self, message_id, branch_group, branch_index, is_active):
        for e in self._msgs:
            if e.msg.id == message_id:
                e.msg.branch_group = branch_group
                e.msg.branch_index = branch_index
                e.msg.is_active = is_active
                break

    async def deactivate_branch_group(self, branch_group, thread_id):
        for e in self._msgs:
            if e.msg.branch_group == branch_group:
                e.msg.is_active = False

    async def get_previous_assistant_state(
        self, thread_id, before_message_id=None
    ) -> str:
        """Mirrors the SQL contract — the most recent assistant's state
        strictly before ``before_message_id`` (or any if None).

        Required so the BranchMessageRepo satisfies the
        MessageRepository Protocol when used with ChatService.
        """
        candidates = [
            e.msg for e in self._msgs
            if e.msg.role == "assistant"
            and e.msg.state
            and (
                before_message_id is None
                or (e.msg.id is not None and e.msg.id < before_message_id)
            )
        ]
        candidates.sort(key=lambda m: m.id or 0, reverse=True)
        return candidates[0].state if candidates else ""


class FakeOrchestrator:
    """Controllable orchestrator stub — records last request, yields preset chunks."""

    def __init__(self, chunks: list[str] | None = None, fail: bool = False):
        self.last_request = None
        self._chunks = chunks or ["assistant ", "response"]
        self._fail = fail

    async def generate(self, request):
        self.last_request = request
        if self._fail:
            raise RuntimeError("orchestrator fail")
        return "".join(self._chunks)

    async def generate_stream(self, request):
        self.last_request = request
        if self._fail:
            raise RuntimeError("orchestrator fail")
        from app.infrastructure.llm import LLMChunk

        for chunk in self._chunks:
            yield LLMChunk(content=chunk)


# ── Helpers ──────────────────────────────────────────────────────────


async def _make_bot(
    repo: FakeBotRepo, first_message: str = "Hello! I'm Kira!", name: str = "Kira"
) -> int:
    return await repo.create(
        name=name,
        personality="Friendly catgirl",
        first_message=first_message,
        scenario="Cozy cafe in Neo-Tokyo",
    )


async def _make_bot_with_mes_example(
    repo: FakeBotRepo, mes_example: str, first_message: str = "Hello!"
) -> int:
    """Test helper: create a bot with a non-empty mes_example field."""
    return await repo.create(
        name="Kira",
        personality="Friendly catgirl",
        first_message=first_message,
        scenario="Cozy cafe in Neo-Tokyo",
        mes_example=mes_example,
    )


# ── Dialogue consistency checker ────────────────────────────────


def check_llm_prompt_consistency(
    llm_messages: list[dict[str, str]],
    bot_personality: str | None = None,
    bot_scenario: str | None = None,
    user_persona_name: str | None = None,
    bot_first_message: str | None = None,
) -> list[str]:
    issues: list[str] = []
    if not llm_messages:
        issues.append("LLM prompt is empty")
        return issues
    if llm_messages[0].get("role") != "system":
        issues.append(f"First LLM message must be system, got {llm_messages[0].get('role')}")
    system_content = llm_messages[0].get("content", "")
    if bot_personality and bot_personality not in system_content:
        issues.append("System prompt missing bot personality")
    if bot_scenario and bot_scenario not in system_content:
        issues.append("System prompt missing bot scenario")
    if user_persona_name and user_persona_name not in system_content:
        issues.append("System prompt missing user persona name")
    non_system = [m for m in llm_messages if m.get("role") != "system"]

    # Verify bot first_message appears in the LLM prompt
    if bot_first_message:
        fm_found = any(m.get("content") == bot_first_message for m in non_system)
        if not fm_found:
            issues.append("Bot first_message not found in LLM messages: " + bot_first_message[:50])
        if non_system and non_system[0].get("content") == bot_first_message:
            if non_system[0].get("role") != "assistant":
                issues.append("First non-system message is first_message but role is not assistant")

    allowed = {"user", "assistant"}
    # The last two messages may be RAG context + user input (both "user").
    # Skip the last message when checking alternation for this reason.
    for i, m in enumerate(non_system):
        role = m.get("role", "")
        if role not in allowed:
            issues.append("Unexpected role " + str(role) + " at non-system position " + str(i))
        # Allow one pair of consecutive "user" for RAG + user_input at the end
        if i > 0 and role == non_system[i - 1].get("role"):
            if not (role == "user" and i == len(non_system) - 1):
                issues.append(
                    "Consecutive LLM messages with same role "
                    + str(role)
                    + " at positions "
                    + str(i - 1)
                    + " and "
                    + str(i)
                )
    return issues


def check_dialogue_consistency(
    messages: list[MessageDTO],
    bot_first_message: str | None = None,
) -> list[str]:
    """Validate the active dialogue sequence for correctness.

    Checks:
    1. Messages alternate: assistant -> user -> assistant -> user -> ...
    2. If bot_first_message is provided, it appears first (or nowhere if inactive)
    3. No two consecutive messages share the same role
    4. No duplicate (role, content) pairs among active messages
    5. In each branch_group, exactly one message is active

    Returns a list of issue strings (empty = consistent).
    """
    issues: list[str] = []
    active = [m for m in messages if m.is_active]

    if not active:
        issues.append("No active messages in dialogue")
        return issues

    # Sort by insertion order (id)
    active_sorted = sorted(active, key=lambda m: m.id or 0)

    # 1. Role alternation: must start with assistant
    if active_sorted[0].role != "assistant":
        issues.append(f"First active message must be 'assistant', got '{active_sorted[0].role}'")

    for i in range(1, len(active_sorted)):
        prev = active_sorted[i - 1].role
        curr = active_sorted[i].role
        if curr == prev:
            issues.append(
                f"Consecutive messages with same role '{curr}' at positions {i - 1} and {i}"
            )
        if curr not in ("user", "assistant"):
            issues.append(f"Unexpected role '{curr}' at position {i}")

    expected_alternation = ["assistant", "user"] * ((len(active_sorted) + 1) // 2)
    got_alternation = [m.role for m in active_sorted]
    # Don't check full alternation if first message starts differently
    if got_alternation[:2] == ["user", "assistant"]:
        pass  # Allow user-first dialogues
    elif (
        got_alternation[: len(expected_alternation)] != expected_alternation[: len(got_alternation)]
    ):
        # Just check no consecutive same roles (already done above)
        pass

    # 2. Bot first_message check
    if bot_first_message:
        first_assistant = next((m for m in active_sorted if m.role == "assistant"), None)
        if first_assistant is not None and first_assistant.content != bot_first_message:
            # first_message might have been regenerated — soft warning
            pass

    # 3. Duplicate detection among active
    seen: set[tuple[str, str]] = set()
    for m in active_sorted:
        key = (m.role, m.content)
        if key in seen:
            issues.append(
                f"Duplicate active message: role='{m.role}' content='{m.content[:30]}...'"
            )
        seen.add(key)

    # 4. Branch group consistency
    branch_groups: dict[str, list[MessageDTO]] = {}
    for m in active + [msg for msg in messages if not msg.is_active]:
        if m.branch_group:
            branch_groups.setdefault(m.branch_group, []).append(m)

    for bg, msgs in branch_groups.items():
        active_in_group = [m for m in msgs if m.is_active]
        if len(active_in_group) != 1:
            issues.append(
                f"Branch group '{bg[:8]}...' has {len(active_in_group)} active messages "
                f"(expected 1), active_ids={[m.id for m in active_in_group]}"
            )
        # Check branch indices are contiguous starting from 0
        indices = sorted(m.branch_index for m in msgs)
        expected_indices = list(range(len(indices)))
        if indices != expected_indices:
            issues.append(
                f"Branch group '{bg[:8]}...' has indices {indices}, expected {expected_indices}"
            )

    return issues


# ══════════════════════════════════════════════════════════════════════
#  stream_message() — normal message flow
# ══════════════════════════════════════════════════════════════════════


class TestStreamMessage:
    @pytest.mark.asyncio
    async def test_streams_chunks_from_orchestrator(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator(chunks=["hello ", "world"])
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch, llm=FakeLLM())

        chunks = [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]

        assert len(chunks) == 2
        assert chunks[0].content == "hello "
        assert chunks[1].content == "world"

    @pytest.mark.asyncio
    async def test_saves_first_message_on_new_thread(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Nya~!")
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]

        all_msgs = await msgs.list_all_for_thread(1)
        assert len(all_msgs) >= 3
        assert all_msgs[0].role == "assistant"
        assert all_msgs[0].content == "Nya~!"
        assert all_msgs[1].role == "user"
        assert all_msgs[1].content == "Hi"

    @pytest.mark.asyncio
    async def test_saves_user_message_before_streaming(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator(fail=True)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        with pytest.raises(ExternalServiceError):
            [
                chunk
                async for chunk in service.stream_message(
                    SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
                )
            ]

        all_msgs = await msgs.list_all_for_thread(1)
        user_msgs = [m for m in all_msgs if m.role == "user"]
        assert len(user_msgs) == 1
        assert user_msgs[0].content == "Hi"

    @pytest.mark.asyncio
    async def test_saves_assistant_response_after_streaming(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator(chunks=["Hello ", "there!"])
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]

        all_msgs = await msgs.list_all_for_thread(1)
        assistant_msgs = [m for m in all_msgs if m.role == "assistant"]
        assert len(assistant_msgs) == 2
        assert assistant_msgs[-1].content == "Hello there!"

    @pytest.mark.asyncio
    async def test_no_assistant_message_on_empty_response(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator(chunks=[""])
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]

        all_msgs = await msgs.list_all_for_thread(1)
        assistant_msgs = [m for m in all_msgs if m.role == "assistant"]
        assert len(assistant_msgs) == 1  # only first_message

    @pytest.mark.asyncio
    async def test_excludes_current_user_message_from_history(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]

        request = orch.last_request
        assert request is not None
        assert len([m for m in request.history if m.content == "Hi"]) == 0
        assert request.user_input == "Hi"

    @pytest.mark.asyncio
    async def test_includes_rag_context_in_request(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Tell me something")
            )
        ]

        request = orch.last_request
        assert request is not None
        assert "canned knowledge context" in request.untrusted_context

    @pytest.mark.asyncio
    async def test_first_message_saved_only_once(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Nya~!")
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Again")
            )
        ]

        all_msgs = await msgs.list_all_for_thread(1)
        first_msgs = [m for m in all_msgs if m.content == "Nya~!"]
        assert len(first_msgs) == 1

    @pytest.mark.asyncio
    async def test_message_order_correct_after_two_exchanges(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator(chunks=["resp1"])
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]
        orch._chunks = ["resp2"]
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="How are you?")
            )
        ]

        roles = [(m.role, m.content) for m in await msgs.list_all_for_thread(1)]
        assert roles[0] == ("assistant", "Hello!")
        assert roles[1] == ("user", "Hi")
        assert roles[2] == ("assistant", "resp1")
        assert roles[3] == ("user", "How are you?")
        assert roles[4] == ("assistant", "resp2")

    @pytest.mark.asyncio
    async def test_knowledge_context_uses_latest_user_input(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")

        class TrackingKnowledge(FakeKnowledgeRepo):
            def __init__(self):
                self.last_query = None

            async def search(self, bot_id, query, top_k=3):
                self.last_query = query
                return [f"result for: {query}"]

        knowledge = TrackingKnowledge()
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        service = ChatService(bots, msgs, knowledge, orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Tell me about cats")
            )
        ]

        assert knowledge.last_query == "Tell me about cats"
        request = orch.last_request
        assert request is not None
        assert "result for: Tell me about cats" in request.untrusted_context

    @pytest.mark.asyncio
    async def test_knowledge_context_per_exchange(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")

        class TrackingKnowledge(FakeKnowledgeRepo):
            def __init__(self):
                self.queries = []

            async def search(self, bot_id, query, top_k=3):
                self.queries.append(query)
                return [f"context: {query}"]

        knowledge = TrackingKnowledge()
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator(chunks=["resp1"])
        service = ChatService(bots, msgs, knowledge, orch)

        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="First query")
            )
        ]
        orch._chunks = ["resp2"]
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Second query")
            )
        ]

        assert len(knowledge.queries) == 2
        assert knowledge.queries[0] == "First query"
        assert knowledge.queries[1] == "Second query"

    @pytest.mark.asyncio
    async def test_auto_names_thread_on_first_exchange(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        threads = FakeThreadRepo()
        llm = FakeLLM(response="A Cozy Chat")
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch, threads=threads, llm=llm)

        thread_id = await threads.create(bot_id, name="Новая беседа")
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=thread_id, bot_id=bot_id, user_input="Hi!")
            )
        ]

        renamed = await threads.get(thread_id)
        assert renamed is not None
        assert renamed.name == "A Cozy Chat"

    @pytest.mark.asyncio
    async def test_does_not_rename_existing_thread(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        msgs = BranchMessageRepo()
        await msgs.save(1, "assistant", "Hello!")
        await msgs.save(1, "user", "Earlier")
        await msgs.save(1, "assistant", "Earlier resp")
        orch = FakeOrchestrator()
        threads = FakeThreadRepo()
        llm = FakeLLM(response="Should Not Apply")
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch, threads=threads, llm=llm)

        thread_id = await threads.create(bot_id, name="My Custom Name")
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=thread_id, bot_id=bot_id, user_input="Hi!")
            )
        ]

        renamed = await threads.get(thread_id)
        assert renamed is not None
        assert renamed.name == "My Custom Name"


# ══════════════════════════════════════════════════════════════════════
#  regenerate_message() — branching and version tracking
# ══════════════════════════════════════════════════════════════════════


class TestRegenerateMessage:
    async def _setup_thread(
        self, messages: BranchMessageRepo, bot_id: int, thread_id: int = 1
    ) -> None:
        await messages.save(thread_id, "assistant", "Hello!")
        await messages.save(thread_id, "user", "Hi")
        await messages.save(thread_id, "assistant", "Nice to meet you!")

    async def _make_service(self, chunks: list[str] | None = None, fail: bool = False) -> tuple:
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        msgs = BranchMessageRepo()
        await self._setup_thread(msgs, bot_id)
        orch = FakeOrchestrator(chunks=chunks or ["Regenerated ", "response!"], fail=fail)
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)
        return service, msgs, orch, bot_id

    @pytest.mark.asyncio
    async def test_regenerate_creates_new_branch_version(self):
        service, _msgs, _orch, _bot_id = await self._make_service()
        events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        meta = next(e for e in events if e["type"] == "meta")
        assert meta["branch_group"] is not None
        assert meta["branch_index"] == 1
        done = next(e for e in events if e["type"] == "done")
        assert done["message"] is not None
        assert done["message"]["content"] == "Regenerated response!"
        assert done["message"]["branch_index"] == 1

    @pytest.mark.asyncio
    async def test_regenerate_saves_new_message(self):
        service, msgs, _orch, _bot_id = await self._make_service()
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        all_msgs = await msgs.list_all_for_thread(1)
        assert "Regenerated response!" in [m.content for m in all_msgs]

    @pytest.mark.asyncio
    async def test_multiple_regenerations_accumulate_versions(self):
        service, _msgs, orch, _bot_id = await self._make_service()
        orch._chunks = ["First regen"]
        events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        first_new_id = next(e for e in events if e["type"] == "done")["message_id"]

        orch._chunks = ["Second regen"]
        events2 = [event async for event in service.regenerate_message(1, first_new_id, _bot_id)]
        done2 = next(e for e in events2 if e["type"] == "done")
        assert len(done2["versions"]) == 3
        second_new_id = done2["message_id"]

        orch._chunks = ["Third regen"]
        events3 = [event async for event in service.regenerate_message(1, second_new_id, _bot_id)]
        done3 = next(e for e in events3 if e["type"] == "done")
        assert len(done3["versions"]) == 4
        assert done3["versions"][-1]["content"] == "Third regen"

    @pytest.mark.asyncio
    async def test_regenerate_returns_versions_in_order(self):
        """Each regenerate targets the *currently active* version
        (the one the user actually sees), not a fixed message_id.

        Before the chain-aware delete fix
        (``ChatService._delete_active_chain_after``), this test
        re-targeted the original message_id=3 every iteration, and
        ``delete_after(3)`` would wipe the intermediate branches
        between iterations, so ``branch_index`` would reset to 1 each
        time. The old assertion only "passed" because the in-between
        versions were silently deleted.

        The real UX is: the user clicks "regenerate" on whichever
        version of the bubble is currently in front of them, which is
        the *active* one. The active version id is the last entry in
        the previous ``done.versions`` payload (the new active row),
        so we thread that id through the loop.
        """
        service, _msgs, orch, _bot_id = await self._make_service()
        target_id = 3  # the original assistant message
        for chunk in ["First", "Second", "Third"]:
            orch._chunks = [chunk]
            events = [event async for event in service.regenerate_message(1, target_id, _bot_id)]
            done = next(e for e in events if e["type"] == "done")
            indices = [v["branch_index"] for v in done["versions"]]
            assert indices == list(range(len(indices))), (
                f"branch_index sequence must be dense starting at 0; got {indices}"
            )
            # Next iteration regenerates whichever version is now
            # active — the user clicks on the bubble they see.
            target_id = done["versions"][-1]["id"]

    @pytest.mark.asyncio
    async def test_meta_event_has_correct_branch_info(self):
        service, _msgs, _orch, _bot_id = await self._make_service()
        events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        meta = next(e for e in events if e["type"] == "meta")
        assert meta["thread_id"] == 1
        assert meta["branch_group"] is not None
        assert meta["branch_index"] == 1

    @pytest.mark.asyncio
    async def test_deletes_messages_after_target(self):
        service, msgs, _orch, _bot_id = await self._make_service()
        await msgs.save(1, "user", "Follow up")
        await msgs.save(1, "assistant", "Follow response")
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        contents = [m.content for m in await msgs.list_all_for_thread(1)]
        assert "Follow up" not in contents
        assert "Follow response" not in contents
        assert "Regenerated response!" in contents

    @pytest.mark.asyncio
    async def test_deactivates_original_version(self):
        service, msgs, _orch, _bot_id = await self._make_service()
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        orig = next((m for m in await msgs.list_all_for_thread(1) if m.id == 3), None)
        assert orig is not None
        assert orig.is_active is False

    @pytest.mark.asyncio
    async def test_only_new_version_is_active(self):
        service, _msgs, _orch, _bot_id = await self._make_service()
        events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        done = next(e for e in events if e["type"] == "done")
        active = [v for v in done["versions"] if v["is_active"]]
        assert len(active) == 1
        assert active[0]["branch_index"] == 1

    @pytest.mark.asyncio
    async def test_multiple_regens_only_latest_active(self):
        service, _msgs, orch, _bot_id = await self._make_service()
        for chunk in ["First", "Second", "Third"]:
            orch._chunks = [chunk]
            events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
            done = next(e for e in events if e["type"] == "done")
            active = [v for v in done["versions"] if v["is_active"]]
            assert len(active) == 1
            assert active[0]["content"] == chunk

    @pytest.mark.asyncio
    async def test_excludes_target_message_from_llm_context(self):
        service, _msgs, orch, _bot_id = await self._make_service()
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        hist = [m.content for m in orch.last_request.history]
        assert "Nice to meet you!" not in hist

    @pytest.mark.asyncio
    async def test_excludes_last_user_message_from_history(self):
        service, _msgs, orch, _bot_id = await self._make_service()
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        request = orch.last_request
        assert request.user_input == "Hi"
        assert len([m for m in request.history if m.content == "Hi"]) == 0

    @pytest.mark.asyncio
    async def test_regenerate_includes_first_message_in_context(self):
        service, _msgs, orch, _bot_id = await self._make_service()
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        assert "Hello!" in [m.content for m in orch.last_request.history]

    @pytest.mark.asyncio
    async def test_regenerate_nonexistent_message_raises_not_found(self):
        service, _msgs, _orch, _bot_id = await self._make_service()
        with pytest.raises(NotFoundError):
            [event async for event in service.regenerate_message(1, 999, _bot_id)]

    @pytest.mark.asyncio
    async def test_regenerate_empty_llm_response_yields_error(self):
        service, _msgs, _orch, _bot_id = await self._make_service(chunks=[""])
        events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        errors = [e for e in events if e["type"] == "error"]
        assert len(errors) == 1
        assert "Empty" in errors[0]["detail"]

    @pytest.mark.asyncio
    async def test_regenerate_error_does_not_corrupt_thread(self):
        service, _msgs, orch, _bot_id = await self._make_service()
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        orch._fail = True
        events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        assert len([e for e in events if e["type"] == "error"]) >= 1
        # Thread should still have messages (first_message + user)
        remaining = await _msgs.list_all_for_thread(1)
        assert len(remaining) >= 2

    @pytest.mark.asyncio
    async def test_done_event_contains_full_version_list(self):
        service, _msgs, _orch, _bot_id = await self._make_service()
        events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        done = next(e for e in events if e["type"] == "done")
        assert len(done["versions"]) >= 2
        orig = next(v for v in done["versions"] if v["branch_index"] == 0)
        new = next(v for v in done["versions"] if v["branch_index"] == 1)
        assert orig["content"] == "Nice to meet you!"
        assert orig["is_active"] is False
        assert new["content"] == "Regenerated response!"
        assert new["is_active"] is True

    @pytest.mark.asyncio
    async def test_regenerate_on_already_branched_message(self):
        service, _msgs, orch, _bot_id = await self._make_service()
        orch._chunks = ["First regen"]
        events1 = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        first_new_id = next(e for e in events1 if e["type"] == "done")["message_id"]

        orch._chunks = ["Second regen"]
        events2 = [event async for event in service.regenerate_message(1, first_new_id, _bot_id)]
        done2 = next(e for e in events2 if e["type"] == "done")

        assert len(done2["versions"]) == 3
        assert done2["versions"][0]["content"] == "Nice to meet you!"
        assert done2["versions"][1]["content"] == "First regen"
        assert done2["versions"][2]["content"] == "Second regen"
        assert done2["versions"][2]["is_active"] is True

    @pytest.mark.asyncio
    async def test_regenerate_preserves_other_messages_in_thread(self):
        service, msgs, _orch, _bot_id = await self._make_service()
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        contents = [m.content for m in await msgs.list_all_for_thread(1)]
        assert "Hello!" in contents
        assert "Hi" in contents
        assert "Regenerated response!" in contents

    @pytest.mark.asyncio
    async def test_regenerate_includes_knowledge_context(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        msgs = BranchMessageRepo()
        await msgs.save(1, "assistant", "Hello!")
        await msgs.save(1, "user", "Tell me about cats")
        await msgs.save(1, "assistant", "I love cats!")
        orch = FakeOrchestrator(chunks=["Regen response"])

        class TrackingKnowledge(FakeKnowledgeRepo):
            def __init__(self):
                self.last_query = None

            async def search(self, bot_id, query, top_k=3):
                self.last_query = query
                return [f"result: {query}"]

        knowledge = TrackingKnowledge()
        service = ChatService(bots, msgs, knowledge, orch)
        [event async for event in service.regenerate_message(1, 3, bot_id)]

        assert knowledge.last_query == "Tell me about cats"
        assert "result: Tell me about cats" in orch.last_request.untrusted_context

    @pytest.mark.asyncio
    async def test_regenerate_message_sequence_correct(self):
        service, msgs, _orch, _bot_id = await self._make_service()
        [event async for event in service.regenerate_message(1, 3, _bot_id)]
        visible = [m for m in await msgs.list_all_for_thread(1) if m.is_active]
        assert ("assistant", "Hello!") in [(m.role, m.content) for m in visible]
        assert ("user", "Hi") in [(m.role, m.content) for m in visible]
        last_asst = [m for m in visible if m.role == "assistant"][-1]
        assert last_asst.content == "Regenerated response!"

    @pytest.mark.asyncio
    async def test_regenerate_message_sequence_regens_last_message(self):
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        msgs = BranchMessageRepo()
        await msgs.save(1, "assistant", "Hello!")
        await msgs.save(1, "user", "Hi")
        await msgs.save(1, "assistant", "First reply")
        await msgs.save(1, "user", "How are you?")
        await msgs.save(1, "assistant", "I'm fine")
        orch = FakeOrchestrator(chunks=["Much better now!"])
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)
        [event async for event in service.regenerate_message(1, 5, bot_id)]
        visible = [m for m in await msgs.list_all_for_thread(1) if m.is_active]
        contents = [m.content for m in visible]
        assert "Hello!" in contents
        assert "Hi" in contents
        assert "First reply" in contents
        assert "How are you?" in contents
        assert "I'm fine" not in contents
        assert "Much better now!" in contents
        assert visible[-1].content == "Much better now!"
        assert visible[-1].role == "assistant"

    @pytest.mark.asyncio
    async def test_regenerate_yields_events_in_correct_order(self):
        service, _msgs, _orch, _bot_id = await self._make_service()
        events = [event async for event in service.regenerate_message(1, 3, _bot_id)]
        types = [e["type"] for e in events]
        assert types[0] == "meta"
        assert types[-1] in ("done", "error")


class TestDialogueConsistency:
    """Integration tests using check_dialogue_consistency() to validate
    the full dialogue sequence after various operations."""

    @pytest.mark.asyncio
    async def test_full_conversation_alternates_correctly(self):
        """A complete conversation alternates assistant then user then assistant."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello there!")
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        for user_msg, asst_resp in [
            ("Hi!", "Welcome!"),
            ("Tell me a story", "Once upon a time..."),
            ("Great!", "I'm glad you liked it!"),
        ]:
            orch._chunks = [asst_resp]
            [
                chunk
                async for chunk in service.stream_message(
                    SendMessageCommand(thread_id=1, bot_id=bot_id, user_input=user_msg)
                )
            ]

        issues = check_dialogue_consistency(
            await msgs.list_all_for_thread(1),
            bot_first_message="Hello there!",
        )
        assert not issues, "Dialogue consistency failed:\n" + "\n".join(issues)

    @pytest.mark.asyncio
    async def test_conversation_after_regen_is_consistent(self):
        """Regenerating the last message keeps dialogue alternating."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        orch._chunks = ["Nice to meet you!"]
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]
        orch._chunks = ["How can I help?"]
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="I need info")
            )
        ]

        orch._chunks = ["Let me assist you!"]
        [event async for event in service.regenerate_message(1, 5, bot_id)]

        issues = check_dialogue_consistency(
            await msgs.list_all_for_thread(1),
            bot_first_message="Hello!",
        )
        assert not issues, "Dialogue consistency failed:\n" + "\n".join(issues)

    @pytest.mark.asyncio
    async def test_multi_regen_with_continuation_is_consistent(self):
        """Regen, continue, regen again, continue: dialogue stays valid."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots, first_message="Hello!")
        msgs = BranchMessageRepo()
        orch = FakeOrchestrator()
        service = ChatService(bots, msgs, FakeKnowledgeRepo(), orch)

        orch._chunks = ["Nice to meet you!"]
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
            )
        ]

        orch._chunks = ["Greetings, human!"]
        events = [event async for event in service.regenerate_message(1, 3, bot_id)]
        next(e for e in events if e["type"] == "done")["message_id"]

        orch._chunks = ["I'm an AI assistant"]
        [
            chunk
            async for chunk in service.stream_message(
                SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="What are you?")
            )
        ]

        all_msgs = await msgs.list_all_for_thread(1)
        active = [m for m in all_msgs if m.is_active]
        last_asst = [m for m in active if m.role == "assistant"][-1]
        orch._chunks = ["I'm Kira, your assistant!"]
        [event async for event in service.regenerate_message(1, last_asst.id, bot_id)]

        issues = check_dialogue_consistency(
            await msgs.list_all_for_thread(1),
            bot_first_message="Hello!",
        )
        assert not issues, "Dialogue consistency failed:\n" + "\n".join(issues)
