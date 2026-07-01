"""Tests for reasoning-content separation in OpenRouterLLM.

Regression: ``_extract_delta_text`` used ``delta.get("content") or
delta.get("reasoning_content")`` which leaks the model's internal
chain-of-thought to the user when the API streams reasoning in
``delta.reasoning_content`` with an empty ``delta.content``.

The fix: return a typed ``LLMChunk`` that splits content and reasoning
into separate fields, and route them through the orchestrator to the
ChatChunk DTO so the frontend can render them independently.
"""

from collections.abc import AsyncGenerator  # noqa: F401 — kept for future tests

import pytest

from app.infrastructure.llm import OpenRouterLLM, _split_delta


class TestSplitDelta:
    """Pure-function unit tests for the reasoning/content splitter."""

    def test_content_only_chunk(self) -> None:
        chunk, reasoning = _split_delta({"content": "Hello"})
        assert chunk == "Hello"
        assert reasoning is None

    def test_reasoning_only_chunk_does_not_leak_to_content(self) -> None:
        """The bug: empty content + reasoning_content used to surface as content."""
        chunk, reasoning = _split_delta({"content": "", "reasoning_content": "Hmm..."})
        assert chunk == "", "reasoning_content must NOT leak into content"
        assert reasoning == "Hmm..."

    def test_reasoning_with_missing_content(self) -> None:
        """Some providers omit content entirely while reasoning is active."""
        chunk, reasoning = _split_delta({"reasoning_content": "Thinking..."})
        assert chunk == ""
        assert reasoning == "Thinking..."

    def test_empty_delta_yields_empty_strings(self) -> None:
        chunk, reasoning = _split_delta({})
        assert chunk == ""
        assert reasoning is None

    def test_both_present_keeps_them_separate(self) -> None:
        chunk, reasoning = _split_delta(
            {"content": "Final answer", "reasoning_content": "Step 1..."}
        )
        assert chunk == "Final answer"
        assert reasoning == "Step 1..."


class TestStreamSplitsReasoning:
    """End-to-end: stream_response splits reasoning into a separate channel.

    Uses a fake httpx stream to drive two SSE chunks: one with reasoning
    only, one with content only. Verifies the OpenRouterLLM yields them
    as separate LLMChunks with the fields correctly populated.
    """

    @pytest.mark.asyncio
    async def test_stream_emits_reasoning_separate_from_content(self) -> None:
        sse_payload = (
            'data: {"choices":[{"delta":{"content":"","reasoning_content":"Hmm "}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"Hi","reasoning_content":""}}]}\n\n'
            "data: [DONE]\n\n"
        )

        llm = OpenRouterLLM(api_key="")

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            async def aiter_lines(self):
                for line in sse_payload.splitlines(keepends=False):
                    yield line

        class _ClientStub:
            def stream(self, method, url, **kwargs):
                return _FakeStreamCtx(_Resp())

        class _FakeStreamCtx:
            def __init__(self, resp):
                self.resp = resp

            async def __aenter__(self):
                return self.resp

            async def __aexit__(self, *exc):
                return None

        llm._get_async_client = lambda: _ClientStub()  # type: ignore[method-assign]

        chunks: list = []
        async for c in llm.generate_response_stream([{"role": "user", "content": "hi"}]):
            chunks.append(c)

        # First chunk: reasoning only. Second chunk: content only.
        assert len(chunks) == 2, f"expected 2 chunks, got {len(chunks)}: {chunks}"
        assert chunks[0].content == ""
        assert chunks[0].reasoning == "Hmm "
        assert chunks[1].content == "Hi"
        assert chunks[1].reasoning == ""

        # Critical invariant: reasoning text must never appear in .content
        leaked = [c for c in chunks if c.content and "Hmm" in c.content]
        assert not leaked, f"reasoning leaked into content: {leaked}"


class TestNonStreamSplitsReasoning:
    """Regression: non-streaming generate_response must never use
    ``reasoning_content`` as the user-visible content.

    When a reasoning model (DeepSeek, QwQ, o1-style) finishes with
    ``content: null`` and a populated ``reasoning_content``, the old
    code used ``or`` to fall back to reasoning, which then leaked
    internal chain-of-thought into the persisted message and
    inflated ``short_content`` with model thoughts.
    """

    @pytest.mark.asyncio
    async def test_non_stream_returns_empty_when_only_reasoning(self) -> None:
        """The bug: empty content + reasoning_content used to surface as content."""
        body = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning_content": "Hmm... I should think about this...",
                    }
                }
            ]
        }

        llm = OpenRouterLLM(api_key="")

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return body

        class _ClientStub:
            def __init__(self):
                self.resp = _Resp()

            async def post(self, url, headers=None, json=None):
                return self.resp

            async def aclose(self):
                return None

        llm._async_client = _ClientStub()

        result = await llm.generate_response([{"role": "user", "content": "hi"}])
        assert result == "", f"reasoning_content must NOT leak into content; got: {result!r}"

    @pytest.mark.asyncio
    async def test_non_stream_returns_empty_content_when_content_empty_string(
        self,
    ) -> None:
        """Some providers return ``content: ""`` alongside active reasoning."""
        body = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": "Thinking...",
                    }
                }
            ]
        }

        llm = OpenRouterLLM(api_key="")

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return body

        class _ClientStub:
            def __init__(self):
                self.resp = _Resp()

            async def post(self, url, headers=None, json=None):
                return self.resp

            async def aclose(self):
                return None

        llm._async_client = _ClientStub()

        result = await llm.generate_response([{"role": "user", "content": "hi"}])
        assert result == "", f"empty content must not fall back to reasoning; got: {result!r}"

    @pytest.mark.asyncio
    async def test_non_stream_keeps_content_when_both_present(self) -> None:
        """Normal case: content + reasoning both populated, return content."""
        body = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "Final answer",
                        "reasoning_content": "Step 1...",
                    }
                }
            ]
        }

        llm = OpenRouterLLM(api_key="")

        class _Resp:
            status_code = 200

            def raise_for_status(self):
                return None

            def json(self):
                return body

        class _ClientStub:
            def __init__(self):
                self.resp = _Resp()

            async def post(self, url, headers=None, json=None):
                return self.resp

            async def aclose(self):
                return None

        llm._async_client = _ClientStub()

        result = await llm.generate_response([{"role": "user", "content": "hi"}])
        assert result == "Final answer"
