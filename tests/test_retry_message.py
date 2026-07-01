"""Regression test for the retry_message LLMChunk serialization bug.

The bug: ChatService.retry_message iterated over orchestrator.generate_stream()
(typed as AsyncGenerator[LLMChunk]) but treated each item as a str, yielding
``{"type": "chunk", "content": <LLMChunk>}`` into the SSE stream. The route
then called ``json.dumps(event)`` on it, which crashed with
"Object of type LLMChunk is not JSON serializable".

The fix: in retry_message, read ``llm_chunk.content`` (and optionally
``llm_chunk.reasoning``) from the LLMChunk object before yielding — the same
pattern that stream_message and regenerate_message already use.

These tests pin down the contract: the values yielded to the SSE consumer
must be plain dicts whose ``content`` field is a ``str`` (so the route's
``json.dumps(event)`` doesn't blow up) and the final persisted message must
be the joined visible content (not a repr of LLMChunk).
"""

from types import SimpleNamespace

from app.application.dto import MessageDTO
from app.application.services.chat import ChatService


class _FakeOrchestrator:
    """Yields LLMChunk objects, mimicking the real generate_stream contract."""

    def __init__(self, contents: list[str], reasonings: list[str | None] | None = None) -> None:
        self.contents = contents
        self.reasonings = reasonings or [None] * len(contents)

    async def generate_stream(self, request):
        from app.infrastructure.llm import LLMChunk

        for content, reasoning in zip(self.contents, self.reasonings, strict=True):
            yield LLMChunk(content=content, reasoning=reasoning)


class _FakeMessages:
    def __init__(self, user_message: MessageDTO) -> None:
        self._user = user_message
        self.saved: list[dict] = []
        self.deleted: list[tuple[int, int]] = []

    async def list_for_thread(self, thread_id, limit=20):
        return [self._user]

    async def delete_after(self, thread_id, message_id):
        self.deleted.append((thread_id, message_id))

    async def save(self, thread_id, role, content, **kwargs) -> int:
        self.saved.append({"thread_id": thread_id, "role": role, "content": content, **kwargs})
        return len(self.saved)


class _FakeBots:
    async def get(self, bot_id):
        return SimpleNamespace(
            id=bot_id,
            name="TestBot",
            personality="",
            scenario="",
            first_message="",
            bot_type=None,
        )


class _FakeKnowledge:
    async def search(self, bot_id, query, top_k):
        return []


def _make_service(messages, orch) -> ChatService:
    return ChatService(
        bots=_FakeBots(),
        messages=messages,
        knowledge=_FakeKnowledge(),
        orchestrator=orch,
        personas=None,
        threads=None,
        llm=None,
        files=None,
        summarizer=None,
    )


async def test_retry_message_yields_string_content_for_each_chunk():
    """Each yielded chunk must have content: str (JSON-serializable).

    Regression: the bug yielded the LLMChunk object directly, breaking
    json.dumps in the SSE route.
    """
    user_msg = MessageDTO(
        id=7,
        role="user",
        content="hi",
        branch_group=None,
        branch_index=0,
        is_active=True,
        generation_status="complete",
    )
    messages = _FakeMessages(user_msg)
    orch = _FakeOrchestrator(contents=["hello ", "world", "!"])
    service = _make_service(messages, orch)

    events = []
    async for event in service.retry_message(
        thread_id=42, user_message_id=7, bot_id=1, persona_id=None
    ):
        events.append(event)

    chunk_events = [e for e in events if e.get("type") == "chunk"]
    assert len(chunk_events) == 3, f"expected 3 chunks, got {events}"
    assert [e["content"] for e in chunk_events] == ["hello ", "world", "!"], (
        f"content must be the LLMChunk.content string, not the LLMChunk object: {chunk_events}"
    )


async def test_retry_message_persists_joined_visible_content():
    """After retry_message completes, the persisted message must be the
    concatenation of LLMChunk.content strings — not a repr of the objects
    or the literal 'LLMChunk(...)' string.
    """
    user_msg = MessageDTO(
        id=7,
        role="user",
        content="hi",
        branch_group=None,
        branch_index=0,
        is_active=True,
        generation_status="complete",
    )
    messages = _FakeMessages(user_msg)
    orch = _FakeOrchestrator(contents=["hello ", "world"])
    service = _make_service(messages, orch)

    async for _ in service.retry_message(
        thread_id=42, user_message_id=7, bot_id=1, persona_id=None
    ):
        pass  # drain

    assistant_saves = [s for s in messages.saved if s.get("role") == "assistant"]
    assert len(assistant_saves) == 1, f"expected one assistant save, got {messages.saved}"
    persisted = assistant_saves[0]["content"]
    assert persisted == "hello world", (
        f"persisted content must be the joined text, got {persisted!r}"
    )
    assert "LLMChunk" not in persisted, "persisted content must not contain LLMChunk repr"


async def test_retry_message_done_event_after_successful_stream():
    """On success, retry_message must yield a final 'done' event so the
    client can finalize the message in the UI."""
    user_msg = MessageDTO(
        id=7,
        role="user",
        content="hi",
        branch_group=None,
        branch_index=0,
        is_active=True,
        generation_status="complete",
    )
    messages = _FakeMessages(user_msg)
    orch = _FakeOrchestrator(contents=["ok"])
    service = _make_service(messages, orch)

    events = []
    async for event in service.retry_message(
        thread_id=42, user_message_id=7, bot_id=1, persona_id=None
    ):
        events.append(event)

    assert any(e.get("type") == "done" for e in events), (
        f"retry_message must yield a 'done' event on success, got {events}"
    )
