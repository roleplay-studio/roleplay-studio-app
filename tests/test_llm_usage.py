"""Tests for token-usage extraction in OpenRouterLLM.

OpenAI-compatible streaming APIs (and OpenRouter, which mirrors them) emit
a final SSE chunk carrying a ``usage`` object once the model finishes
generating, with prompt_tokens / completion_tokens / total_tokens. We
need to surface these so the dev-mode chat modal can show the user how
many tokens each request burned.

When the provider omits usage (cheap/free models, or callers that didn't
opt in via ``stream_options.include_usage``), the chunks simply come
through with ``usage=None`` — the modal gracefully hides its footer in
that case.
"""

import pytest

from app.infrastructure.llm import LLMChunk, OpenRouterLLM


def _make_llm_with_sse_payload(sse_payload: str) -> OpenRouterLLM:
    """Build an OpenRouterLLM that streams a canned SSE response.

    The pattern mirrors the one in test_reasoning_separation.py — a
    fake httpx async-stream context that yields the provided lines.
    """
    llm = OpenRouterLLM(api_key="")

    class _Resp:
        status_code = 200

        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            for line in sse_payload.splitlines(keepends=False):
                yield line

    class _FakeStreamCtx:
        def __init__(self, resp):
            self.resp = resp

        async def __aenter__(self):
            return self.resp

        async def __aexit__(self, *exc):
            return None

    class _ClientStub:
        def stream(self, method, url, **kwargs):
            return _FakeStreamCtx(_Resp())

    llm._get_async_client = lambda: _ClientStub()  # type: ignore[method-assign]
    return llm


class TestStreamUsageExtraction:
    """The final SSE chunk's ``usage`` block must surface on the
    terminal LLMChunk so the dev modal can show token counts."""

    @pytest.mark.asyncio
    async def test_final_chunk_carries_usage(self) -> None:
        """When the provider emits a usage block in the terminal chunk,
        the LLM must yield a final LLMChunk whose ``usage`` field is
        populated with prompt/completion/total counts."""
        sse_payload = (
            'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":" there"}}]}\n\n'
            'data: {"choices":[],'
            '"usage":{"prompt_tokens":42,"completion_tokens":7,'
            '"total_tokens":49}}\n\n'
            "data: [DONE]\n\n"
        )
        llm = _make_llm_with_sse_payload(sse_payload)

        chunks: list[LLMChunk] = []
        async for c in llm.generate_response_stream([{"role": "user", "content": "hi"}]):
            chunks.append(c)

        # The last yielded chunk must carry the usage block.
        last = chunks[-1]
        assert last.usage == {
            "prompt_tokens": 42,
            "completion_tokens": 7,
            "total_tokens": 49,
        }, f"expected usage on final chunk, got: {last}"

    @pytest.mark.asyncio
    async def test_intermediate_chunks_have_no_usage(self) -> None:
        """Usage is a property of the terminal chunk only. Intermediate
        content/reasoning chunks must not bleed usage into earlier
        emissions (would force the UI to render token counts that change
        mid-stream)."""
        sse_payload = (
            'data: {"choices":[{"delta":{"content":"A"}}]}\n\n'
            'data: {"choices":[{"delta":{"content":"B"}}]}\n\n'
            'data: {"choices":[],'
            '"usage":{"prompt_tokens":10,"completion_tokens":2,'
            '"total_tokens":12}}\n\n'
            "data: [DONE]\n\n"
        )
        llm = _make_llm_with_sse_payload(sse_payload)

        chunks: list[LLMChunk] = []
        async for c in llm.generate_response_stream([{"role": "user", "content": "hi"}]):
            chunks.append(c)

        # All but the last chunk must have usage=None.
        for c in chunks[:-1]:
            assert c.usage is None, f"intermediate chunk leaked usage: {c}"

    @pytest.mark.asyncio
    async def test_no_usage_block_yields_none(self) -> None:
        """When the provider omits the usage block entirely (free tiers,
        or callers without stream_options.include_usage), the stream
        still completes cleanly with usage=None on every chunk."""
        sse_payload = 'data: {"choices":[{"delta":{"content":"Hi"}}]}\n\ndata: [DONE]\n\n'
        llm = _make_llm_with_sse_payload(sse_payload)

        chunks: list[LLMChunk] = []
        async for c in llm.generate_response_stream([{"role": "user", "content": "hi"}]):
            chunks.append(c)

        assert all(c.usage is None for c in chunks)
        assert len(chunks) == 1
        assert chunks[0].content == "Hi"


class TestLLMChunkUsageField:
    """LLMChunk.usage is optional and defaults to None for callers that
    don't care about it (summarization, embedding-adjacent helpers)."""

    def test_default_is_none(self):
        chunk = LLMChunk(content="hi")
        assert chunk.usage is None

    def test_can_be_constructed_with_usage(self):
        chunk = LLMChunk(
            content="",
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
        )
        assert chunk.usage == {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
        }
