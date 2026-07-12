"""Tests for the markdown-repair integration in ChatService.

The repair runs on the assembled ``response`` string just before
it is persisted via ``MessageRepository.save`` /
``save_branch``. The SSE stream the client sees during generation
is untouched — only what lands in the database is cleaned up.

Scope:
  - ``_repair_for_rp`` helper: unit tests for the bot_type filter
    (RP → repair; assistant / agent / None → pass-through).
  - ``ChatService.stream_message`` integration: an RP bot whose
    LLM cuts off mid-bold lands a repaired (closed) message in
    the message repo; an assistant bot with the same broken input
    lands the broken text unchanged.
  - ``FormatStandartRpRepairer`` (infrastructure adapter): smoke
    test that it delegates to ``format_standart_rp.fix_markdown``.

The downstream library is tested in the format-standart-rp
project itself; here we only verify the integration contract.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.application.dto import SendMessageCommand
from app.application.services.chat import (
    ChatService,
    _NullMarkdownRepairer,
    _repair_for_rp,
)
from app.infrastructure.format_standart_rp_repairer import FormatStandartRpRepairer

# ── Unit tests for _repair_for_rp ──────────────────────────────────────


class TestRepairForRpFilter:
    """``_repair_for_rp`` should call repairer.repair only for RP bots."""

    def test_rp_string_calls_repair(self) -> None:
        calls: list[str] = []

        class _SpyRepairer:
            def repair(self, text: str, mode: str = "close") -> str:
                calls.append(text)
                return text + "!"

        out = _repair_for_rp(_SpyRepairer(), "rp", "hello **broken")
        assert calls == ["hello **broken"]
        assert out == "hello **broken!"

    def test_rp_enum_calls_repair(self) -> None:
        from app.domain.enums import BotType

        calls: list[str] = []

        class _SpyRepairer:
            def repair(self, text: str, mode: str = "close") -> str:
                calls.append(text)
                return text

        out = _repair_for_rp(_SpyRepairer(), BotType.RP, "hello **broken")
        assert calls == ["hello **broken"]
        assert out == "hello **broken"

    def test_assistant_passes_through_unchanged(self) -> None:
        calls: list[str] = []

        class _SpyRepairer:
            def repair(self, text: str, mode: str = "close") -> str:
                calls.append(text)
                return text

        out = _repair_for_rp(_SpyRepairer(), "assistant", "hello **broken")
        # Repairer never invoked.
        assert calls == []
        # Text returned verbatim.
        assert out == "hello **broken"

    def test_agent_passes_through_unchanged(self) -> None:
        calls: list[str] = []

        class _SpyRepairer:
            def repair(self, text: str, mode: str = "close") -> str:
                calls.append(text)
                return text

        out = _repair_for_rp(_SpyRepairer(), "agent", "hello **broken")
        assert calls == []
        assert out == "hello **broken"

    def test_none_passes_through_unchanged(self) -> None:
        """Conservative: unknown bot_type → no repair."""

        class _SpyRepairer:
            def __init__(self) -> None:
                self.invoked = False

            def repair(self, text: str, mode: str = "close") -> str:
                self.invoked = True
                return text

        spy = _SpyRepairer()
        out = _repair_for_rp(spy, None, "hello **broken")
        assert spy.invoked is False
        assert out == "hello **broken"

    def test_empty_text_returns_empty_without_calling_repair(self) -> None:
        """No work for empty text — applies regardless of bot_type."""

        class _SpyRepairer:
            def __init__(self) -> None:
                self.invoked = False

            def repair(self, text: str, mode: str = "close") -> str:
                self.invoked = True
                return text

        spy = _SpyRepairer()
        assert _repair_for_rp(spy, "rp", "") == ""
        assert spy.invoked is False


# ── Infrastructure adapter smoke test ─────────────────────────────────


class TestFormatStandartRpRepairer:
    """The adapter must delegate to the library and produce valid output.

    Pinned against the prose-style ``format_roleplay`` helper
    (intentionally chosen over ``fix_markdown`` — it normalises
    asterisks around actions and quotation marks around speech,
    which fits the roleplay chat use-case better).
    """

    def test_repair_delegates_to_library(self) -> None:
        repairer = FormatStandartRpRepairer()
        # The headline bug: LLM cuts off mid-bold. ``format_roleplay``
        # normalises the unclosed ``**`` to a single ``*`` italic
        # wrapper so the resulting text is at least well-formed.
        out = repairer.repair("он сказал **и улыбнулся")
        assert out == "*он сказал **и улыбнулся*"

    def test_unknown_mode_propagates_value_error(self) -> None:
        # ``format_roleplay`` doesn't take a ``mode`` arg — unknown
        # values are silently ignored. Pin that behaviour so a
        # future refactor to a mode-aware helper doesn't surprise
        # callers (they currently rely on no exception, and the
        # chat service is set up to swallow the ValueError only
        # when one is raised).
        repairer = FormatStandartRpRepairer()
        out = repairer.repair("hello", mode="explode")
        assert out == "*hello*"


# ── Null repairer (default fallback) ──────────────────────────────────


class TestNullMarkdownRepairer:
    """The no-op fallback must satisfy the Protocol structurally."""

    def test_returns_text_unchanged(self) -> None:
        nr = _NullMarkdownRepairer()
        assert nr.repair("any text **") == "any text **"
        assert nr.repair("", mode="strip") == ""


# ── Integration tests for ChatService ──────────────────────────────────


class _FakeBotRepo:
    """Minimal bot repo: stores one bot, returns it on get."""

    def __init__(self, bot_type: str = "rp"):
        self._bot = SimpleNamespace(
            id=1,
            name="TestBot",
            bot_type=bot_type,
            first_message="hi",
            personality="A friendly companion",
            scenario="Cozy setting",
            description="",
            mes_example="",
        )

    async def get(self, bot_id: int):
        return self._bot if bot_id == 1 else None

    async def create(self, **kwargs):
        return 1

    async def list(self):
        return [self._bot]

    async def delete(self, bot_id):
        pass

    async def update(self, bot_id, **kwargs):
        pass


class _FakeMessagesRepo:
    """Captures every saved message so tests can assert on them."""

    def __init__(self):
        self.saved: list[dict] = []
        # ``dynamic_system_prompt`` is the newest field — chat
        # production stamps it on assistant messages. Older tests
        # predate it; accept (and ignore) any future keyword args
        # rather than keep the fake in lockstep with every Protocol
        # addition.
        self.states: dict[int, str] = {}

    async def save(
        self,
        thread_id: int,
        role: str,
        content: str,
        branch_group=None,
        branch_index=0,
        is_active=True,
        timestamp=None,
        generation_status: str = "complete",
        reasoning: str | None = None,
        dynamic_system_prompt: str | None = None,
        **_extra: object,
    ) -> int:
        self.saved.append(
            {
                "thread_id": thread_id,
                "role": role,
                "content": content,
                "generation_status": generation_status,
                "reasoning": reasoning,
            }
        )
        return len(self.saved)

    async def save_branch(self, *args, **kwargs):
        # Used by regenerate_message; delegate to save for the test.
        return await self.save(*args, **kwargs)

    async def list_for_thread(self, *args, **kwargs):
        return []

    async def save_first_assistant_if_absent(self, *args, **kwargs):
        return None

    async def save_exchange(self, *args, **kwargs):
        return None

    async def get_versions(self, *args, **kwargs):
        return []


class _FakeKnowledge:
    async def search(self, *args, **kwargs):
        return []

    async def has_documents(self, *args, **kwargs):
        return False


class _FakeOrchestrator:
    """Yields the chunks passed at construction time."""

    def __init__(self, chunks: list[str]):
        self._chunks = chunks

    async def generate_stream(self, request):
        from app.infrastructure.llm import LLMChunk

        for c in self._chunks:
            yield LLMChunk(content=c)

    async def generate(self, request):
        return "".join(self._chunks)


class _SpyRepairer:
    """Repairer that records every call AND transforms the text.

    Mirrors the real ``format-standart-rp`` semantics: count ``**``
    occurrences. Odd → unclosed, append one. Even → balanced,
    return unchanged. This way the spy can be used to assert on
    "was the repairer called" without lying about the result.
    """

    def __init__(self):
        self.calls: list[str] = []

    def repair(self, text: str, mode: str = "close") -> str:
        self.calls.append(text)
        n = text.count("**")
        if n % 2 == 1:
            return text + "**"
        return text


@pytest.mark.asyncio
async def test_stream_message_rp_bot_repairs_unclosed_bold() -> None:
    """Headline integration test: RP bot, LLM cuts off mid-bold → repaired."""
    bots = _FakeBotRepo(bot_type="rp")
    msgs = _FakeMessagesRepo()
    orch = _FakeOrchestrator(chunks=["Он сказал **тихо и улыбнулся"])
    repairer = _SpyRepairer()

    service = ChatService(
        bots,
        msgs,
        _FakeKnowledge(),
        orch,
        markdown_repairer=repairer,
    )

    # Drain the stream.
    async for _ in service.stream_message(
        SendMessageCommand(thread_id=1, bot_id=1, user_input="привет")
    ):
        pass

    # The assistant message is the one with role='assistant' and status='complete'.
    assistant_msgs = [m for m in msgs.saved if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] == "Он сказал **тихо и улыбнулся**"

    # The repairer was called once with the broken string.
    assert repairer.calls == ["Он сказал **тихо и улыбнулся"]


@pytest.mark.asyncio
async def test_stream_message_assistant_bot_does_not_repair() -> None:
    """assistant bot → repairer never invoked, text persisted as-is."""
    bots = _FakeBotRepo(bot_type="assistant")
    msgs = _FakeMessagesRepo()
    orch = _FakeOrchestrator(chunks=["Он сказал **тихо и улыбнулся"])
    repairer = _SpyRepairer()

    service = ChatService(
        bots,
        msgs,
        _FakeKnowledge(),
        orch,
        markdown_repairer=repairer,
    )

    async for _ in service.stream_message(
        SendMessageCommand(thread_id=1, bot_id=1, user_input="привет")
    ):
        pass

    assistant_msgs = [m for m in msgs.saved if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] == "Он сказал **тихо и улыбнулся"

    # Repairer was never called for an assistant bot.
    assert repairer.calls == []


@pytest.mark.asyncio
async def test_stream_message_agent_bot_does_not_repair() -> None:
    """agent bot → same as assistant: no repair, raw text in DB."""
    bots = _FakeBotRepo(bot_type="agent")
    msgs = _FakeMessagesRepo()
    orch = _FakeOrchestrator(chunks=["**broken"])
    repairer = _SpyRepairer()

    service = ChatService(
        bots,
        msgs,
        _FakeKnowledge(),
        orch,
        markdown_repairer=repairer,
    )

    async for _ in service.stream_message(
        SendMessageCommand(thread_id=1, bot_id=1, user_input="hi")
    ):
        pass

    assistant_msgs = [m for m in msgs.saved if m["role"] == "assistant"]
    assert len(assistant_msgs) == 1
    assert assistant_msgs[0]["content"] == "**broken"
    assert repairer.calls == []


@pytest.mark.asyncio
async def test_chat_service_uses_null_repairer_when_not_provided() -> None:
    """Backward compat: ChatService constructed without explicit repairer
    gets a no-op fallback (default), so no repair happens regardless
    of bot_type."""
    bots = _FakeBotRepo(bot_type="rp")
    msgs = _FakeMessagesRepo()
    orch = _FakeOrchestrator(chunks=["**broken"])

    service = ChatService(bots, msgs, _FakeKnowledge(), orch)

    async for _ in service.stream_message(
        SendMessageCommand(thread_id=1, bot_id=1, user_input="hi")
    ):
        pass

    assistant_msgs = [m for m in msgs.saved if m["role"] == "assistant"]
    assert assistant_msgs[0]["content"] == "**broken"


@pytest.mark.asyncio
async def test_stream_message_balanced_markdown_passes_through_unchanged() -> None:
    """Well-formed markdown is not modified by the repairer."""
    bots = _FakeBotRepo(bot_type="rp")
    msgs = _FakeMessagesRepo()
    orch = _FakeOrchestrator(chunks=["Он сказал **тихо** и улыбнулся"])
    repairer = _SpyRepairer()

    service = ChatService(
        bots,
        msgs,
        _FakeKnowledge(),
        orch,
        markdown_repairer=repairer,
    )

    async for _ in service.stream_message(
        SendMessageCommand(thread_id=1, bot_id=1, user_input="привет")
    ):
        pass

    assistant_msgs = [m for m in msgs.saved if m["role"] == "assistant"]
    assert assistant_msgs[0]["content"] == "Он сказал **тихо** и улыбнулся"
    # SpyRepairer IS called for RP bots (even on balanced text); but it
    # detects "ends with **" and returns unchanged.
    assert repairer.calls == ["Он сказал **тихо** и улыбнулся"]
