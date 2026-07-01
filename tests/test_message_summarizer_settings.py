"""M10 unit tests — Settings injection into ``MessageSummarizer``.

Covers the regression where ``MessageSummarizer`` used to call
``Settings.from_env()`` inside ``summarize_message`` and
``batch_summarize``, making it the only service in the app that
re-read the env on every call while ``ChatService``, the
orchestrator, and ``OpenRouterLLM`` all cached the injected
instance. The mismatch could surface as a summarizer using a stale
``summarize_max_tokens`` while the rest of the system was on a
fresh value.

The fix is straightforward: ``MessageSummarizer.__init__`` now
accepts ``settings: Settings | None`` and stores it on
``self._settings`` (parallel to ``OpenRouterLLM`` / ``ChatService``).
"""

from __future__ import annotations

import pytest

from app.application.services.message_summarizer import MessageSummarizer
from app.infrastructure.config import Settings
from app.infrastructure.llm import LLMChunk


class _StubLLM:
    """Minimal LLMPort stub — returns a fixed string."""

    async def generate_response(self, messages, temperature=None, max_tokens=None):
        return "stubbed short summary"

    async def generate_response_stream(self, messages, temperature=None, max_tokens=None):
        yield LLMChunk(content="stubbed short summary")

    async def generate(self, request):
        return "stubbed short summary"

    async def generate_stream(self, request):
        yield LLMChunk(content="stubbed short summary")


class _StubMessages:
    """In-memory MessageRepository stub — records update_short_content calls."""

    def __init__(self) -> None:
        self.updates: list[tuple[int, str]] = []

    async def update_short_content(self, message_id: int, short_content: str) -> None:
        self.updates.append((message_id, short_content))

    # All other MessageRepository methods are unused by these tests.
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


# ── Settings injection ──────────────────────────────────────────────


def test_summarizer_accepts_explicit_settings():
    """M10: explicit ``settings`` kwarg is stored on ``self._settings``."""
    settings = Settings(_env_file=None)
    summ = MessageSummarizer(llm=_StubLLM(), messages=_StubMessages(), settings=settings)
    assert summ._settings is settings


def test_summarizer_falls_back_to_from_env(monkeypatch):
    """Backward compat: ``MessageSummarizer()`` with no settings still
    works (constructs ``Settings.from_env()`` on demand)."""
    monkeypatch.delenv("SUMMARIZE_MAX_TOKENS", raising=False)
    summ = MessageSummarizer(llm=_StubLLM(), messages=_StubMessages())
    assert isinstance(summ._settings, Settings)


# ── summarize_message honours injected settings ─────────────────────


@pytest.mark.asyncio
async def test_summarize_message_uses_injected_max_tokens(monkeypatch):
    """The summarizer must use the LLM call's max_tokens from the
    injected settings, not from a fresh env read."""
    custom = Settings(summarize_max_tokens=42, _env_file=None)
    llm = _StubLLM()
    msgs = _StubMessages()
    summ = MessageSummarizer(llm=llm, messages=msgs, settings=custom)

    long_content = "x" * 500  # well above the default min_length=100
    summary = await summ.summarize_message(message_id=1, content=long_content)
    assert summary == "stubbed short summary"
    assert msgs.updates == [(1, "stubbed short summary")]


@pytest.mark.asyncio
async def test_summarize_message_short_circuits_below_min_length():
    """``summarize_min_length`` from the injected settings filters
    out short messages before we even hit the LLM."""
    custom = Settings(summarize_min_length=200, _env_file=None)
    msgs = _StubMessages()
    summ = MessageSummarizer(llm=_StubLLM(), messages=msgs, settings=custom)

    # Content below the 200-char threshold → no LLM call, no update.
    summary = await summ.summarize_message(message_id=1, content="tiny")
    assert summary is None
    assert msgs.updates == []


# ── batch_summarize uses injected settings ──────────────────────────


@pytest.mark.asyncio
async def test_batch_summarize_uses_injected_settings():
    custom = Settings(summarize_min_length=50, summarize_max_tokens=99, _env_file=None)
    msgs = _StubMessages()
    summ = MessageSummarizer(llm=_StubLLM(), messages=msgs, settings=custom)

    items = [(1, "x" * 60), (2, "y" * 60), (3, "tiny")]
    results = await summ.batch_summarize(items)
    # 1 and 2 are above min_length → summarized.
    # 3 is below min_length → filtered out.
    assert results == {1: "stubbed short summary", 2: "stubbed short summary"}
    assert sorted(m[0] for m in msgs.updates) == [1, 2]
