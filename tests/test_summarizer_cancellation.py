"""m7 unit tests — ``MessageSummarizer`` honours ``asyncio.CancelledError``.

Covers the bug where the broad ``except Exception:`` blocks in
``summarize_message`` / ``summarize_thread_recent`` /
``batch_summarize`` would silently swallow the cancellation when
the task is awaited inside ``asyncio.gather(..., return_exceptions=True)``.
The fix: an explicit ``except asyncio.CancelledError: raise`` block
*before* the broad except.

These tests intentionally don't run the actual LLM call — they
inject a stub that raises CancelledError, then assert the
summarizer re-raises (or, for ``batch_summarize``, surfaces the
exception via the gather return value).

Note (review2.md): ``batch_summarize`` previously downgraded a
cancelled item to a log line and continued with the rest of the
batch. That was a deliberate trade-off documented inline, but it
breaks the cancellation contract: when the parent task is cancelled,
we must propagate so the caller's ``await`` sees the cancellation
instead of silently returning a partial ``results`` dict. The fix
re-raises the first ``CancelledError`` from the gather; the test
below is updated to expect it.
"""

from __future__ import annotations

import asyncio

import pytest

from app.application.dto import MessageDTO
from app.application.services.message_summarizer import MessageSummarizer
from app.infrastructure.config import Settings
from app.infrastructure.llm import LLMChunk


class _CancelledLLM:
    """LLM stub that raises CancelledError immediately."""

    async def generate_response(self, messages, temperature=None, max_tokens=None):
        raise asyncio.CancelledError("simulated abort")

    async def generate_response_stream(self, messages, temperature=None, max_tokens=None):
        raise asyncio.CancelledError("simulated abort")
        yield LLMChunk(content="")  # pragma: no cover — for type checker

    async def generate(self, request):
        raise asyncio.CancelledError("simulated abort")

    async def generate_stream(self, request):
        raise asyncio.CancelledError("simulated abort")
        yield LLMChunk(content="")  # pragma: no cover — for type checker


class _StubMessages:
    def __init__(self) -> None:
        self.updates: list[tuple[int, str]] = []

    async def update_short_content(self, message_id: int, short_content: str) -> None:
        self.updates.append((message_id, short_content))

    async def save(self, *args, **kwargs):
        raise NotImplementedError

    async def save_first_assistant_if_absent(self, *args, **kwargs):
        return True

    async def list_for_thread(self, *args, **kwargs):
        return []

    async def clear_thread(self, *args, **kwargs):
        return None

    async def update(self, *args, **kwargs):
        return None

    async def delete(self, *args, **kwargs):
        return None

    async def get_first_assistant(self, *args, **kwargs):
        return None


@pytest.mark.asyncio
async def test_summarize_message_re_raises_cancelled_error():
    """The fix for m7: CancelledError propagates so the caller's
    ``await`` sees the cancellation instead of silently returning None."""
    settings = Settings(summarize_min_length=10, _env_file=None)
    summ = MessageSummarizer(llm=_CancelledLLM(), messages=_StubMessages(), settings=settings)

    long_content = "x" * 500  # well above min_length
    with pytest.raises(asyncio.CancelledError):
        await summ.summarize_message(message_id=1, content=long_content)


@pytest.mark.asyncio
async def test_summarize_thread_recent_re_raises_cancelled_error():
    settings = Settings(_env_file=None)
    summ = MessageSummarizer(llm=_CancelledLLM(), messages=_StubMessages(), settings=settings)

    msgs = [
        MessageDTO(id=1, role="user", content="x" * 100, short_content=None, timestamp=None),
        MessageDTO(id=2, role="assistant", content="y" * 100, short_content=None, timestamp=None),
    ]
    with pytest.raises(asyncio.CancelledError):
        await summ.summarize_thread_recent(thread_id=1, recent_messages=msgs)


@pytest.mark.asyncio
async def test_batch_summarize_propagates_cancelled_error():
    """review2.md: ``asyncio.gather(..., return_exceptions=True)`` packs
    ``CancelledError`` into a result slot. The outer loop in
    ``batch_summarize`` must re-raise it (instead of silently logging
    and returning a partial ``results`` dict), so the caller's
    ``await`` sees the cancellation. This honours the contract that
    a cancelled parent task does not produce a "successful" result.
    """
    settings = Settings(summarize_min_length=10, _env_file=None)
    summ = MessageSummarizer(llm=_CancelledLLM(), messages=_StubMessages(), settings=settings)

    items = [(1, "x" * 100)]
    with pytest.raises(asyncio.CancelledError):
        await summ.batch_summarize(items)
