"""Unit tests for MessageSummarizer.

Covers the three public methods:
  - summarize_message   (5-15 word summary of a single message)
  - batch_summarize     (parallel summaries of multiple messages)
  - summarize_thread_recent (2-3 sentence thread-level summary)

These tests do NOT touch the real LLM — they use a fake LLMPort
that records calls and returns deterministic strings. The point is
to lock down the orchestration: prompts, return-value parsing,
short_content persistence, batch concurrency, and length-threshold
filtering.
"""

from __future__ import annotations

import asyncio

from app.application.dto import MessageDTO
from app.application.services.message_summarizer import MessageSummarizer

# ── Fakes ──────────────────────────────────────────────────────────────


class FakeLLM:
    """Minimal LLMPort that records calls and returns a stub summary."""

    def __init__(self, response: str = "stub summary") -> None:
        self.response = response
        self.calls: list[dict] = []
        self._delay = 0.0

    async def generate_response(self, messages, temperature=None, max_tokens=None):
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        if self._delay:
            await asyncio.sleep(self._delay)
        return self.response


class FakeMsgRepo:
    """Minimal MessageRepository — records short_content updates."""

    def __init__(self) -> None:
        self.updates: dict[int, str] = {}

    async def update_short_content(self, message_id: int, short_content: str) -> None:
        self.updates[message_id] = short_content

    # Other methods the protocol requires — not used here, raise clearly.
    async def list_for_thread(self, *args, **kwargs):
        raise NotImplementedError

    async def save(self, *args, **kwargs):
        raise NotImplementedError


# ── summarize_message ─────────────────────────────────────────────────


class TestSummarizeMessage:
    async def test_returns_short_summary_and_persists(self):
        llm = FakeLLM(response="Alice seduces her brother in a nightmare loop.")
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        result = await summarizer.summarize_message(42, "long content " * 30)

        assert result == "Alice seduces her brother in a nightmare loop."
        assert repo.updates[42] == "Alice seduces her brother in a nightmare loop."

    async def test_strips_surrounding_quotes(self):
        llm = FakeLLM(response='" hello there "')
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        result = await summarizer.summarize_message(1, "x" * 200)

        assert result == "hello there"
        assert repo.updates[1] == "hello there"

    async def test_skips_short_content_below_min_length(self):
        llm = FakeLLM()
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        result = await summarizer.summarize_message(1, "tiny")

        assert result is None
        assert llm.calls == []  # never even contacted the LLM
        assert 1 not in repo.updates

    async def test_skips_empty_content(self):
        llm = FakeLLM()
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        result = await summarizer.summarize_message(1, "")

        assert result is None
        assert llm.calls == []

    async def test_returns_none_when_llm_returns_empty(self):
        llm = FakeLLM(response="   ")
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        result = await summarizer.summarize_message(1, "x" * 200)

        # Whitespace-only response is treated as no summary.
        assert result is None
        assert 1 not in repo.updates

    async def test_prompt_targets_user_message_role(self):
        llm = FakeLLM(response="ok")
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        await summarizer.summarize_message(1, "x" * 200)

        assert len(llm.calls) == 1
        call = llm.calls[0]
        assert call["messages"][0]["role"] == "system"
        assert call["messages"][1]["role"] == "user"
        assert "5-15 words" in call["messages"][1]["content"]
        assert "x" * 200 in call["messages"][1]["content"]


# ── batch_summarize ────────────────────────────────────────────────────


class TestBatchSummarize:
    async def test_processes_all_items_in_parallel(self):
        llm = FakeLLM(response="ok")
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        items = [(i, f"message {i}: " + "x" * 200) for i in range(6)]
        result = await summarizer.batch_summarize(items, max_concurrent=3)

        # 6 items, all returned "ok"
        assert len(result) == 6
        assert all(v == "ok" for v in result.values())
        # All 6 persisted
        assert len(repo.updates) == 6

    async def test_filters_short_items_before_calling_llm(self):
        llm = FakeLLM(response="ok")
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        items = [
            (1, "x" * 200),  # eligible
            (2, "tiny"),  # skipped
            (3, "x" * 200),  # eligible
            (4, ""),  # skipped (empty)
        ]
        result = await summarizer.batch_summarize(items)

        assert len(result) == 2
        assert 1 in result and 3 in result
        assert 2 not in result and 4 not in result
        assert len(llm.calls) == 2  # only 2 LLM calls, not 4

    async def test_empty_items_returns_empty_dict(self):
        llm = FakeLLM()
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        result = await summarizer.batch_summarize([])

        assert result == {}
        assert llm.calls == []

    async def test_respects_max_concurrency(self):
        """``max_concurrent=1`` should run summaries sequentially."""
        llm = FakeLLM(response="ok")
        llm._delay = 0.05  # 50ms per call
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        items = [(i, "x" * 200) for i in range(3)]

        import time

        t0 = time.perf_counter()
        result = await summarizer.batch_summarize(items, max_concurrent=1)
        elapsed = time.perf_counter() - t0

        # 3 sequential calls x 50ms each = ~150ms minimum.
        # If parallelism leaked, this would be ~50ms.
        assert elapsed >= 0.12, f"expected sequential timing, got {elapsed:.3f}s"
        assert len(result) == 3


# ── summarize_thread_recent ────────────────────────────────────────────


class TestSummarizeThreadRecent:
    async def test_uses_short_content_when_available(self):
        llm = FakeLLM(response="Plot: Alisa and Dim continue their nightmare loop.")
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        messages = [
            MessageDTO(id=1, role="user", content="long " * 50, short_content="Alice scene begins"),
            MessageDTO(
                id=2, role="assistant", content="long " * 50, short_content="Somnia watches"
            ),
        ]
        result = await summarizer.summarize_thread_recent(7, messages)

        assert result == "Plot: Alisa and Dim continue their nightmare loop."
        # short_content should be used in the prompt, not the full content.
        user_prompt = llm.calls[0]["messages"][1]["content"]
        assert "Alice scene begins" in user_prompt
        assert "Somnia watches" in user_prompt
        assert "long long long" not in user_prompt  # full content NOT used

    async def test_falls_back_to_first_500_chars_when_short_content_missing(self):
        llm = FakeLLM(response="plot")
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        # 700-char content, short_content=None
        messages = [
            MessageDTO(
                id=1,
                role="user",
                content="x" * 700,
                short_content=None,
            ),
        ]
        await summarizer.summarize_thread_recent(1, messages)

        user_prompt = llm.calls[0]["messages"][1]["content"]
        # First 500 chars of content used, but no more
        assert user_prompt.count("x") == 500

    async def test_empty_messages_returns_none(self):
        llm = FakeLLM()
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        result = await summarizer.summarize_thread_recent(1, [])

        assert result is None
        assert llm.calls == []

    async def test_caps_at_last_10_messages(self):
        """Even if 20 messages are passed, only the last 10 are sent."""
        llm = FakeLLM(response="summary")
        repo = FakeMsgRepo()
        summarizer = MessageSummarizer(llm, repo)

        # Each message gets a unique sentinel string that is not a
        # substring of any other — needed because ``snippet-1``
        # appears inside ``snippet-10..19`` and a naive ``in`` check
        # would produce false positives.
        messages = [
            MessageDTO(
                id=i,
                role="user" if i % 2 == 0 else "assistant",
                content="x" * 200,
                short_content=f"__S{i}__",
            )
            for i in range(20)
        ]
        await summarizer.summarize_thread_recent(1, messages)

        user_prompt = llm.calls[0]["messages"][1]["content"]
        # First 10 (ids 0..9) should NOT appear; last 10 (ids 10..19) should
        for i in range(10):
            assert f"__S{i}__" not in user_prompt, f"old snippet {i} leaked into prompt"
        for i in range(10, 20):
            assert f"__S{i}__" in user_prompt, f"recent snippet {i} missing from prompt"
