"""Tests for streaming-abort behaviour in ChatService.

Verifies that cancelling an in-flight stream persists the accumulated
chunks as an assistant message with generation_status='stopped'."""

import asyncio
from types import SimpleNamespace

from app.application.dto import MessageDTO, SendMessageCommand
from app.application.services.chat import ChatService
from app.domain.enums import BotType


class _FakeOrchestrator:
    """Yields N chunks, then either returns or blocks (per ``block_after``)."""

    def __init__(self, n: int = 3, block_after: bool = False) -> None:
        self.n = n
        self.block_after = block_after
        self.chunks: list[str] = []
        self._released = asyncio.Event()

    async def generate_stream(self, request):
        from app.infrastructure.llm import LLMChunk

        for i in range(self.n):
            self.chunks.append(f"chunk{i} ")
            yield LLMChunk(content=f"chunk{i} ")
        # Don't block — let the consumer drive cancellation
        # (otherwise the event-loop deadlocks the test runner)


class _FakeMessages:
    """Minimal MessageRepository recording all save() and save_branch() calls."""

    def __init__(self) -> None:
        self.saved: list[dict] = []
        self.branched: list[dict] = []
        self._target_msg = MessageDTO(
            id=7,
            role="assistant",
            content="old content",
            branch_group=None,
            branch_index=0,
            is_active=True,
            generation_status="complete",
        )

    async def save(self, thread_id, role, content, **kwargs) -> int:
        self.saved.append({"thread_id": thread_id, "role": role, "content": content, **kwargs})
        return len(self.saved)

    async def save_branch(
        self, thread_id, role, content, branch_group, branch_index, **kwargs
    ) -> int:
        self.branched.append(
            {
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "branch_group": branch_group,
                "branch_index": branch_index,
                **kwargs,
            }
        )
        return len(self.branched)

    async def list_for_thread(self, thread_id, limit=20):
        return [
            MessageDTO(
                id=999,
                role="user",
                content="hi",
                branch_group=None,
                branch_index=0,
                is_active=True,
                generation_status="complete",
            )
        ]

    async def get_first_assistant(self, thread_id):
        # For abort tests we don't exercise the K4 idempotency path;
        # returning None lets the service save the first_message normally.
        return None

    async def save_first_assistant_if_absent(self, thread_id, content):
        # Stub for RC1.2 — abort tests never reach this path because
        # they don't have a bot with first_message, so just say "no".
        return False

    async def get_versions(self, message_id):
        return [self._target_msg]

    async def update_branch(self, message_id, branch_group, branch_index, is_active=True):
        return None

    async def delete_after(self, thread_id, message_id):
        return None

    async def deactivate_branch_group(self, branch_group, thread_id):
        return None


class _FakeBots:
    async def get(self, bot_id):
        return SimpleNamespace(
            id=bot_id,
            name="TestBot",
            personality="",
            scenario="",
            first_message="",
            bot_type=BotType.RP,
        )


class _FakeKnowledge:
    async def search(self, bot_id, query, top_k=15):
        return []

    async def has_documents(self, bot_id):
        return False



def _make_service(messages: _FakeMessages, orch: _FakeOrchestrator) -> ChatService:
    return ChatService(
        bots=_FakeBots(),  # type: ignore[arg-type]
        messages=messages,  # type: ignore[arg-type]
        knowledge=_FakeKnowledge(),  # type: ignore[arg-type]
        orchestrator=orch,
        personas=None,
        threads=None,
        llm=None,
        files=None,
        summarizer=None,
    )


async def test_stream_message_saves_partial_on_cancellation():
    """Throwing CancelledError into stream_message's await point persists 'stopped'."""
    messages = _FakeMessages()
    # block_after=True so the orchestrator never finishes on its own —
    # the consumer must cancel.
    orch = _FakeOrchestrator(n=2, block_after=True)
    service = _make_service(messages, orch)

    command = SendMessageCommand(thread_id=42, bot_id=1, user_input="hi", persona_id=None)
    gen = service.stream_message(command)

    # Pull the first chunk
    first = await gen.__anext__()
    assert first.content == "chunk0 "

    # Inject CancelledError into the next yield. This is exactly what
    # asyncio.Task.cancel() does on the consumer side — it raises
    # CancelledError at the consumer's await, which propagates through
    # the generator body into the stream-loop's except-arm.
    with __import__("contextlib").suppress(BaseException):
        await gen.athrow(asyncio.CancelledError())

    # The partial should be persisted as status='stopped'
    assistant = [s for s in messages.saved if s.get("role") == "assistant"]
    assert len(assistant) == 1, f"expected 1 assistant save, got {len(assistant)}: {messages.saved}"
    assert assistant[0]["generation_status"] == "stopped"
    assert "chunk0" in assistant[0]["content"]


async def test_regenerate_message_saves_partial_on_cancellation():
    """Throwing CancelledError into stream_branch's await point persists 'stopped'."""
    messages = _FakeMessages()
    orch = _FakeOrchestrator(n=2, block_after=True)
    service = _make_service(messages, orch)

    gen = service.regenerate_message(thread_id=42, message_id=7, bot_id=1, persona_id=None)

    # First event is meta
    meta = await gen.__anext__()
    assert meta["type"] == "meta"

    # Pull a chunk so we're inside the stream-loop's async-for
    chunk_event = await gen.__anext__()
    assert chunk_event["type"] == "chunk"
    assert chunk_event["content"] == "chunk0 "

    # Now inject CancelledError into the next yield
    with __import__("contextlib").suppress(BaseException):
        await gen.athrow(asyncio.CancelledError())

    # The partial should be in save_branch
    assert len(messages.branched) == 1, f"expected 1 branch save, got {len(messages.branched)}"
    assert messages.branched[0]["generation_status"] == "stopped"
    assert "chunk0" in messages.branched[0]["content"]


async def test_stream_message_natural_end_keeps_complete_status():
    """Without cancellation, the assistant message is still saved with status='complete'."""
    messages = _FakeMessages()
    orch = _FakeOrchestrator(n=2, block_after=False)
    service = _make_service(messages, orch)

    command = SendMessageCommand(thread_id=42, bot_id=1, user_input="hi", persona_id=None)
    gen = service.stream_message(command)

    # Drain the generator fully (no cancellation)
    async for _ in gen:
        pass

    assistant = [s for s in messages.saved if s.get("role") == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["generation_status"] == "complete"
    assert assistant[0]["content"] == "chunk0 chunk1 "


async def test_abort_generation_cancels_registered_task_and_persists_partial():
    """abort_generation must find the in-flight stream task in _active_streams,
    cancel it, and let the stream-loop's CancelledError branch save a partial
    message with status='stopped'.

    This is the regression test for the bug where the abort endpoint returned
    was_active=False because nothing ever registered the stream task — the
    user clicked Stop, the server responded 200, but the LLM kept generating
    and the user kept paying for tokens.
    """
    messages = _FakeMessages()
    # Orchestrator yields 1 chunk then blocks forever — the consumer task
    # is what abort_generation will cancel.
    orch = _BlockingOrchestrator()
    service = _make_service(messages, orch)

    command = SendMessageCommand(thread_id=42, bot_id=1, user_input="hi", persona_id=None)

    # Spawn a consumer task that drives the stream and registers itself
    # in _active_streams (mimicking what api/routes/chat.py will do after
    # the fix). It will be cancelled by abort_generation.
    consumer_done = asyncio.Event()
    chunks_seen: list[str] = []

    async def consume_stream() -> None:
        gen = service.stream_message(command)
        task = asyncio.current_task()
        assert task is not None  # we're inside create_task()
        service._active_streams[command.thread_id] = task
        try:
            async for chunk in gen:
                chunks_seen.append(chunk.content)
        finally:
            consumer_done.set()

    consumer_task = asyncio.create_task(consume_stream())
    # Hold a reference so the task isn't garbage-collected mid-stream
    # (RUF006). The actual signal comes from consumer_done.set() in the
    # consume_stream() finally-block.
    consumer_task.add_done_callback(lambda _t: None)
    # Let the consumer pull the first chunk and reach the blocking point
    await asyncio.sleep(0.05)
    assert "chunk0 " in chunks_seen, f"consumer should have received first chunk, got {chunks_seen}"

    # Now abort — should find the registered task, cancel it, and report
    # was_active=True after the consumer's CancelledError branch runs.
    abort_result = await service.abort_generation(command.thread_id)
    await asyncio.wait_for(consumer_done.wait(), timeout=2.0)

    assert abort_result.was_active is True, (
        f"abort should report was_active=True (got {abort_result})"
    )
    assert abort_result.partial_saved is True, (
        f"abort should report partial_saved=True (got {abort_result})"
    )

    # Partial must be persisted as status='stopped'
    assistant = [s for s in messages.saved if s.get("role") == "assistant"]
    assert len(assistant) == 1, f"expected 1 assistant save, got {len(assistant)}: {messages.saved}"
    assert assistant[0]["generation_status"] == "stopped"
    assert "chunk0" in assistant[0]["content"]


async def test_abort_generation_is_noop_when_no_stream_registered():
    """abort on a thread that has no active stream must return was_active=False
    (idempotent) and not raise."""
    messages = _FakeMessages()
    orch = _FakeOrchestrator(n=2)
    service = _make_service(messages, orch)

    result = await service.abort_generation(thread_id=999)
    assert result.was_active is False
    assert result.partial_saved is False


class _BlockingOrchestrator:
    """Yields one chunk, then blocks forever so the test can race abort against it."""

    def __init__(self) -> None:
        self.chunks_emitted = 0

    async def generate_stream(self, request):
        from app.infrastructure.llm import LLMChunk

        yield LLMChunk(content="chunk0 ")
        # Park forever — the only way out of this generator is
        # CancelledError injected from the consumer side.
        await asyncio.Event().wait()
        yield LLMChunk(content="never-reached")  # pragma: no cover


async def test_start_stream_registers_task_for_abort():
    """start_stream() must self-register the spawned task in _active_streams
    so that a subsequent abort_generation() can find and cancel it. This is
    the bug fix: before, the route called stream_message() directly and
    nothing ever landed in _active_streams, so /api/threads/{id}/abort
    always returned was_active=False.
    """
    messages = _FakeMessages()
    orch = _BlockingOrchestrator()
    service = _make_service(messages, orch)

    command = SendMessageCommand(thread_id=42, bot_id=1, user_input="hi", persona_id=None)
    _task, queue = service.start_stream(command)

    # Task must be in the registry right after start_stream returns
    assert command.thread_id in service._active_streams
    assert service._active_streams[command.thread_id] is _task

    # Give the consumer a tick to pull the first chunk
    await asyncio.sleep(0.05)
    first = queue.get_nowait()
    assert first.content == "chunk0 "

    # Abort must find the task and cancel it
    abort_result = await service.abort_generation(command.thread_id)
    # Let the cancelled task finish its finally-block
    try:
        await asyncio.wait_for(asyncio.shield(_task), timeout=2.0)
    except (asyncio.CancelledError, TimeoutError, Exception):
        pass

    # After abort + drain, task must be removed from registry
    assert command.thread_id not in service._active_streams

    # abort result should report the cancel happened
    assert abort_result.was_active is True
    assert abort_result.partial_saved is True

    # And the partial should be persisted as 'stopped'
    assistant = [s for s in messages.saved if s.get("role") == "assistant"]
    assert len(assistant) == 1
    assert assistant[0]["generation_status"] == "stopped"
    assert "chunk0" in assistant[0]["content"]

    # The sentinel None should be in the queue
    sentinel = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert sentinel is None
