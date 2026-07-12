"""Tests for the dev-mode token-usage SSE channel.

The frontend renders a small token-count footer inside the dev-mode LLM
debug modal (assistant message → 🔧 → modal). The data arrives as a
dedicated SSE event of type ``usage`` with a ``usage`` payload shaped
like ``{"prompt_tokens": N, "completion_tokens": N, "total_tokens": N}``.

These tests pin three contracts:
  1. ``ChatChunk`` carries the usage through the application layer.
  2. ``ChatService.stream_message`` forwards it on the terminal chunk.
  3. The route renders a ``type: "usage"`` SSE event when usage is
     populated, and emits nothing when the provider omits usage.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.application.dto import ChatChunk, SendMessageCommand
from app.application.services import ChatService
from app.infrastructure.llm import LLMChunk

# ── Stub helpers (mirror the pattern in test_chat_generation.py) ─────


class _FakeBotRepo:
    """Bot repository stub.

    Stores bots as SimpleNamespace so attribute access
    (``bot.first_message``) matches what ChatService expects.
    """

    def __init__(self):
        self._bots: dict[int, object] = {}
        self._next = 1

    async def get(self, bot_id):
        return self._bots.get(bot_id)

    async def create(self, **kwargs):
        # Provide sensible defaults for fields ChatService reads but the
        # test doesn't always set explicitly (bot_type, scenario, etc.).
        kwargs.setdefault("bot_type", "rp")
        kwargs.setdefault("scenario", "")
        kwargs.setdefault("first_message", "Hello!")
        kwargs.setdefault("personality", "")
        bid = self._next
        self._next += 1
        self._bots[bid] = SimpleNamespace(id=bid, **kwargs)
        return bid


class _FakeMsgRepo:
    async def save(self, *args, **kwargs):
        return 1

    async def save_exchange(self, *args, **kwargs):
        return None

    async def list_for_thread(self, thread_id, limit: int | None = None):
        # Mirrors the real SqlAlchemyMessageRepository signature.
        # ``limit`` is ignored here — the test only needs the call to
        # not crash and to return an empty list.
        return []

    async def get_first_assistant(self, thread_id):
        # K4 idempotency hook — return None so the service saves a
        # first_message normally during stream_message.
        return None

    async def save_first_assistant_if_absent(self, thread_id, content):
        # RC1.2 stub — these tests don't exercise the atomic-insert path.
        return False


class _FakeKnowledgeRepo:
    async def search(self, *args, **kwargs):
        return []

    async def has_documents(self, *args, **kwargs):
        return False


class _StreamingLLM:
    """LLM stub that yields a fixed sequence of LLMChunks.

    Pass ``chunks=[...]`` to control exactly what comes out of the
    stream. The last chunk can carry ``usage`` to simulate OpenRouter's
    terminal usage block.
    """

    def __init__(self, chunks: list[LLMChunk]):
        self._chunks = chunks

    async def generate_response(self, messages, temperature=None, max_tokens=None):
        return "".join(c.content for c in self._chunks)

    async def generate_response_stream(self, messages, temperature=None, max_tokens=None):
        for c in self._chunks:
            yield c


class _StreamingOrchestrator:
    """Passthrough orchestrator — defers to the underlying LLM."""

    def __init__(self, llm: _StreamingLLM):
        self._llm = llm

    async def generate_stream(self, request):
        async for c in self._llm.generate_response_stream([]):
            yield c

    async def generate(self, request):
        return await self._llm.generate_response([])


# ── 1. ChatChunk DTO ─────────────────────────────────────────────────


class TestChatChunkUsageField:
    def test_default_is_none(self):
        chunk = ChatChunk(content="hi")
        assert chunk.usage is None

    def test_can_be_constructed_with_usage(self):
        chunk = ChatChunk(
            content="",
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )
        assert chunk.usage == {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        }


# ── 2. ChatService.stream_message propagates usage ───────────────────


class TestStreamMessagePropagatesUsage:
    @pytest.mark.asyncio
    async def test_terminal_chunk_carries_usage(self):
        """When the LLM yields a terminal chunk with usage, the service
        must forward it unchanged so the route can render a ``usage``
        SSE event."""
        llm = _StreamingLLM(
            chunks=[
                LLMChunk(content="Hi"),
                LLMChunk(content=" there"),
                LLMChunk(
                    content="",
                    usage={
                        "prompt_tokens": 42,
                        "completion_tokens": 7,
                        "total_tokens": 49,
                    },
                ),
            ]
        )
        bots = _FakeBotRepo()
        bot_id = await bots.create(name="t", personality="p", first_message="Hello!")
        service = ChatService(
            bots=bots,
            messages=_FakeMsgRepo(),
            knowledge=_FakeKnowledgeRepo(),
            orchestrator=_StreamingOrchestrator(llm),
        )

        chunks = []
        async for c in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
        ):
            chunks.append(c)

        # The last chunk must carry the usage block. Intermediate chunks
        # are content-only — usage=None there.
        assert chunks[-1].usage == {
            "prompt_tokens": 42,
            "completion_tokens": 7,
            "total_tokens": 49,
        }
        for c in chunks[:-1]:
            assert c.usage is None

    @pytest.mark.asyncio
    async def test_no_usage_chunks_are_none(self):
        """When the provider emits no usage block, every ChatChunk must
        carry usage=None — the route then never yields a ``usage`` SSE
        event."""
        llm = _StreamingLLM(chunks=[LLMChunk(content="Hi"), LLMChunk(content=" there")])
        bots = _FakeBotRepo()
        bot_id = await bots.create(name="t", personality="p", first_message="Hello!")
        service = ChatService(
            bots=bots,
            messages=_FakeMsgRepo(),
            knowledge=_FakeKnowledgeRepo(),
            orchestrator=_StreamingOrchestrator(llm),
        )

        chunks = []
        async for c in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
        ):
            chunks.append(c)

        assert all(c.usage is None for c in chunks)


# ── 3. SSE route renders ``usage`` event ────────────────────────────


def _parse_sse_events(body: str) -> list[dict]:
    """Helper: parse a raw SSE response body into a list of event dicts.

    Mirrors the format the frontend Chat.svelte consumer expects:
    each line ``data: {...}`` becomes one dict, in order.
    """
    events: list[dict] = []
    for raw in body.splitlines():
        line = raw.strip()
        if not line.startswith("data: "):
            continue
        events.append(json.loads(line[6:]))
    return events


class TestRouteRendersUsageEvent:
    """End-to-end: drive the SSE generator function directly (no
    TestClient, no network) and verify the right events come out."""

    @pytest.mark.asyncio
    async def test_emits_usage_event_when_populated(self):
        """A terminal ChatChunk with usage must produce a
        ``type='usage'`` SSE event with the counts inline."""
        from api.routes.chat import _format_chat_chunk_event

        item = ChatChunk(
            content="hi",
            usage={"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        )
        rendered = _format_chat_chunk_event(item)
        events = _parse_sse_events(rendered)

        usage_events = [e for e in events if e.get("type") == "usage"]
        assert len(usage_events) == 1
        assert usage_events[0]["usage"] == {
            "prompt_tokens": 5,
            "completion_tokens": 1,
            "total_tokens": 6,
        }

    @pytest.mark.asyncio
    async def test_omits_usage_event_when_none(self):
        """ChatChunk with usage=None must NOT produce a ``usage`` SSE
        event — providers that skip the block keep the wire clean."""
        from api.routes.chat import _format_chat_chunk_event

        item = ChatChunk(content="hi")
        rendered = _format_chat_chunk_event(item)
        events = _parse_sse_events(rendered)

        assert not any(e.get("type") == "usage" for e in events)


# ── 4. Dev-mode debug payload (LLM request snapshot) ────────────────


class _FakeLLMWithModel:
    """LLM stub that yields the standard test sequence and exposes a
    stable model_name — mirrors what the real OpenRouterLLM does so the
    service can populate ``LLMDebugInfo.model``.
    """

    model_name = "openai/gpt-oss-20b"

    async def generate_response(self, messages, temperature=None, max_tokens=None):
        return "Hi there"

    async def generate_response_stream(self, messages, temperature=None, max_tokens=None):
        from app.infrastructure.llm import LLMChunk

        for chunk in ("Hi", " there"):
            yield LLMChunk(content=chunk)
        # Terminal usage block.
        yield LLMChunk(
            content="",
            usage={"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13},
        )


class _OrchestratorWithPayload:
    """Real-looking orchestrator that yields a debug-messages chunk
    first, then delegates to the LLM. Mirrors the production
    LangGraphConversationOrchestrator behavior."""

    def __init__(self, llm):
        self._llm = llm

    async def generate_stream(self, request):
        from app.infrastructure.llm import LLMChunk

        # Build a deterministic messages list — what the LLM would see.
        messages = [
            {"role": "system", "content": "<Persona>\nFriendly catgirl\n</Persona>"},
            {"role": "user", "content": request.user_input},
        ]
        # First chunk: dev-mode payload side channel.
        yield LLMChunk(content="", debug_messages=messages)
        # Subsequent chunks come from the LLM.
        async for c in self._llm.generate_response_stream([]):
            yield c

    async def generate(self, request):
        return await self._llm.generate_response([])


class TestServiceEmitsDebugPayload:
    """When ``Settings.debug_enabled`` is on, ``ChatService.stream_message``
    must produce a ChatChunk whose ``debug`` field carries the message
    list, model name, and sampling params."""

    @pytest.mark.asyncio
    async def test_first_chunk_carries_debug_when_enabled(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "true")
        llm = _FakeLLMWithModel()
        bots = _FakeBotRepo()
        bot_id = await bots.create(name="t", personality="Friendly catgirl", first_message="Hello!")
        service = ChatService(
            bots=bots,
            messages=_FakeMsgRepo(),
            knowledge=_FakeKnowledgeRepo(),
            orchestrator=_OrchestratorWithPayload(llm),
            llm=llm,
        )

        chunks = []
        async for c in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
        ):
            chunks.append(c)

        # The very first chunk is the dev-mode payload.
        assert chunks[0].debug is not None
        assert chunks[0].debug.model == "openai/gpt-oss-20b"
        assert chunks[0].debug.messages == [
            {"role": "system", "content": "<Persona>\nFriendly catgirl\n</Persona>"},
            {"role": "user", "content": "Hi"},
        ]
        # Only the first chunk carries debug.
        for c in chunks[1:]:
            assert c.debug is None

    @pytest.mark.asyncio
    async def test_no_debug_when_disabled(self, monkeypatch):
        monkeypatch.setenv("DEBUG", "false")
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        llm = _FakeLLMWithModel()
        bots = _FakeBotRepo()
        bot_id = await bots.create(name="t", personality="Friendly catgirl", first_message="Hello!")
        service = ChatService(
            bots=bots,
            messages=_FakeMsgRepo(),
            knowledge=_FakeKnowledgeRepo(),
            orchestrator=_OrchestratorWithPayload(llm),
            llm=llm,
        )

        chunks = []
        async for c in service.stream_message(
            SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="Hi")
        ):
            chunks.append(c)

        # Production: no chunk carries debug, even though the
        # orchestrator still yielded the message list.
        assert all(c.debug is None for c in chunks)


class TestRouteRendersDebugEvent:
    """End-to-end: the route renders a ``type='debug'`` SSE event when
    ``ChatChunk.debug`` is populated, and emits nothing when it's
    ``None`` (production)."""

    def test_emits_debug_event_when_populated(self):
        from api.routes.chat import _format_chat_chunk_event
        from app.application.dto import LLMDebugInfo

        item = ChatChunk(
            content="",
            debug=LLMDebugInfo(
                model="openai/gpt-oss-20b",
                messages=[
                    {"role": "system", "content": "You are a catgirl"},
                    {"role": "user", "content": "Hi"},
                ],
                temperature=0.7,
                max_tokens=4096,
            ),
        )
        events = _parse_sse_events(_format_chat_chunk_event(item))
        debug_events = [e for e in events if e.get("type") == "debug"]
        assert len(debug_events) == 1
        payload = debug_events[0]["debug"]
        assert payload["model"] == "openai/gpt-oss-20b"
        assert payload["messages"] == [
            {"role": "system", "content": "You are a catgirl"},
            {"role": "user", "content": "Hi"},
        ]
        assert payload["temperature"] == 0.7
        assert payload["max_tokens"] == 4096

    def test_omits_debug_event_when_none(self):
        from api.routes.chat import _format_chat_chunk_event

        item = ChatChunk(content="hi")
        events = _parse_sse_events(_format_chat_chunk_event(item))
        assert not any(e.get("type") == "debug" for e in events)

    def test_debug_and_content_can_coexist(self):
        """A chunk that carries both visible content and a debug payload
        must emit BOTH events (one ``chunk`` and one ``debug``). The
        service is free to colocate them, but the route must preserve
        both channels on the wire."""
        from api.routes.chat import _format_chat_chunk_event
        from app.application.dto import LLMDebugInfo

        item = ChatChunk(
            content="hi",
            debug=LLMDebugInfo(model="m", messages=[]),
        )
        events = _parse_sse_events(_format_chat_chunk_event(item))
        types = {e.get("type") for e in events}
        assert "chunk" in types
        assert "debug" in types
