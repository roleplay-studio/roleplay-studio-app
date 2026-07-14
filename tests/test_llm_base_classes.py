"""Tests for the new BaseOpenAICompatibleLLM (Phase 1.2).

Uses httpx.MockTransport — no real network. The base class is
provider-agnostic: it takes api_key, base_url, model explicitly so
the same code drives openrouter/openai/lm-studio/deepseek/...

These tests cover the surface Task 2 needs to verify before we
delete app/infrastructure/llm.py (Task 3): the body shape sent to
{base_url}/chat/completions, the SSE chunk parser, the reasoning
field-name configurability, and LLMChunk immutability (the M11 lesson
that ``list`` in a frozen dataclass was a lie).
"""

from __future__ import annotations

import json

import httpx
import pytest

# NOTE: imports from app.infrastructure.llm.base_openai — these WILL
# FAIL with ModuleNotFoundError until Task 2 creates that file.
from app.infrastructure.llm.base_openai import (
    BaseOpenAICompatibleLLM,
    LLMChunk,
    _extract_usage,
    _split_delta,
)


@pytest.mark.asyncio
async def test_base_posts_to_chat_completions_with_expected_body() -> None:
    """BaseOpenAICompatibleLLM POSTs to {base_url}/chat/completions."""
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content.decode())
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "hi"}, "finish_reason": "stop"}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    llm = BaseOpenAICompatibleLLM(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="test-model",
    )
    llm._async_client = httpx.AsyncClient(transport=transport)
    try:
        out = await llm.generate_response(
            messages=[{"role": "user", "content": "hello"}],
        )
    finally:
        await llm.close()

    assert out == "hi"
    assert captured["url"].endswith("/chat/completions")
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["stream"] is False
    assert captured["body"]["messages"] == [{"role": "user", "content": "hello"}]
    # No api_key → no Authorization header (we test with a real one).
    assert captured["headers"].get("authorization") == "Bearer sk-test"


@pytest.mark.asyncio
async def test_base_streams_sse_chunks_in_order() -> None:
    """Streaming yields (content, reasoning) per delta and a terminal usage chunk."""
    async def handler(request: httpx.Request) -> httpx.Response:
        # Build the OpenAI-style SSE body manually so we exercise both
        # the parsing and the order of events.
        events = [
            'data: {"choices":[{"delta":{"content":"Hel","reasoning":"think1"}}]}',
            'data: {"choices":[{"delta":{"content":"lo!","reasoning":null}}]}',
            'data: {"choices":[],"usage":{"prompt_tokens":5,"completion_tokens":2,"total_tokens":7}}',
            "data: [DONE]",
        ]
        body = "\n".join(events) + "\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    llm = BaseOpenAICompatibleLLM(
        api_key="sk-test",
        base_url="https://example.com/v1",
        model="m",
        reasoning_field_names=["reasoning"],
    )
    llm._async_client = httpx.AsyncClient(transport=transport)
    try:
        chunks = []
        async for c in llm.generate_response_stream(
            messages=[{"role": "user", "content": "hi"}],
        ):
            chunks.append(c)
    finally:
        await llm.close()

    assert len(chunks) == 3
    assert chunks[0].content == "Hel" and chunks[0].reasoning == "think1"
    assert chunks[1].content == "lo!" and chunks[1].reasoning is None
    assert chunks[2].content == "" and chunks[2].usage == {
        "prompt_tokens": 5,
        "completion_tokens": 2,
        "total_tokens": 7,
    }


def test_split_delta_picks_first_named_reasoning_field() -> None:
    """Configurable reasoning field names — first non-empty wins; empty
    content does NOT fall back to reasoning (M3.2 lesson)."""
    content, reasoning = _split_delta(
        {"content": "hi", "thinking": "thought"},
        reasoning_field_names=["thinking"],
    )
    assert content == "hi"
    assert reasoning == "thought"

    # Empty content must stay empty — must NOT be replaced by reasoning.
    content, reasoning = _split_delta(
        {"content": "", "thinking": "thought"},
        reasoning_field_names=["thinking"],
    )
    assert content == ""
    assert reasoning == "thought"


def test_split_delta_first_hit_wins_over_following_names() -> None:
    # When the delta emits multiple reasoning fields, the order of
    # names in ``reasoning_field_names`` decides which one wins.
    _content_unused, reasoning = _split_delta(
        {"content": "x", "raw": "R1", "thought": "R2"},
        reasoning_field_names=["thought", "raw"],  # thought is listed first
    )
    assert reasoning == "R2"  # thought wins over raw


def test_extract_usage_returns_none_on_bad_payload() -> None:
    """Guard against malformed usage blocks — never crashes, returns None."""
    assert _extract_usage({}) is None
    assert _extract_usage({"usage": "not a dict"}) is None
    assert _extract_usage({"usage": {"prompt_tokens": 5}}) is None  # missing keys
    # ``int("5")`` succeeds — strings coercible to int are accepted by
    # historical behaviour (some providers serialise numbers as JSON
    # strings). Truly non-numeric strings raise ValueError → None.
    assert _extract_usage(
        {"usage": {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}}
    ) == {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
    assert _extract_usage(
        {"usage": {"prompt_tokens": "5", "completion_tokens": 2, "total_tokens": 7}}
    ) == {"prompt_tokens": 5, "completion_tokens": 2, "total_tokens": 7}
    assert _extract_usage(
        {"usage": {"prompt_tokens": "not-a-number", "completion_tokens": 2, "total_tokens": 7}}
    ) is None


def test_llm_chunk_is_immutable_with_tuple_debug_messages() -> None:
    """M11 lesson: a frozen dataclass with a list field is a lie. The new
    LLMChunk uses a tuple for debug_messages — actually frozen."""
    chunk = LLMChunk(
        content="x",
        reasoning="y",
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        debug_messages=({"role": "user", "content": "q"},),
    )
    with pytest.raises((AttributeError, TypeError)):
        chunk.content = "mutated"  # type: ignore[misc]
