"""Tests for summarization, versions in list_for_thread, and settings."""

from __future__ import annotations

import os

from app.application.dto import MessageDTO
from app.application.services import ChatService
from app.application.services.message_summarizer import (
    MessageSummarizer,
)
from app.infrastructure.config import Settings

# ── Fake LLM ───────────────────────────────────────────────────────────


class FakeLLM:
    """LLM that returns canned responses and records calls."""

    def __init__(self, response: str = "Canned response."):
        self.response = response
        self.calls: list[dict] = []  # (messages, temperature, max_tokens)

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        return self.response

    async def generate_response_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        from app.infrastructure.llm import LLMChunk

        yield LLMChunk(content=self.response)


# ── Fake repos ─────────────────────────────────────────────────────────


class FakeMessageRepo:
    def __init__(self):
        self._messages: list[MessageDTO] = []
        self._next_id = 1
        self.short_content_updates: list[tuple[int, str]] = []
        self.list_for_thread_calls: list[tuple[int, int | None]] = []  # (thread_id, limit)

    async def save(
        self,
        thread_id,
        role,
        content,
        branch_group=None,
        branch_index=0,
        is_active=True,
        short_content=None,
        timestamp=None,
        generation_status: str = "complete",
    ):
        mid = self._next_id
        self._next_id += 1
        self._messages.append(
            MessageDTO(
                id=mid,
                role=role,
                content=content,
                short_content=short_content,
                branch_group=branch_group,
                branch_index=branch_index,
                is_active=is_active,
                created_at=timestamp,
            )
        )
        return mid

    async def list_for_thread(self, thread_id, limit=20):
        # Record the call so tests can assert on the limit that
        # ``run_summarization`` requested. This guards against the
        # regression where the interval check was performed on a
        # too-narrow ``recent`` window (see regression test below).
        self.list_for_thread_calls.append((thread_id, limit))
        active = [
            m
            for m in self._messages
            if m.id is not None and (m.branch_group is None or m.is_active)
        ]

        # Collect branch_groups from active messages
        branch_groups = {m.branch_group for m in active if m.branch_group}

        # Attach versions to each message with a branch_group
        result: list[MessageDTO] = []
        for m in active:
            dto = MessageDTO(
                id=m.id,
                role=m.role,
                content=m.content,
                short_content=m.short_content,
                branch_group=m.branch_group,
                branch_index=m.branch_index,
                is_active=m.is_active,
            )
            if m.branch_group and m.branch_group in branch_groups:
                dto.versions = [v for v in self._messages if v.branch_group == m.branch_group]
            result.append(dto)
        return result

    async def update_short_content(self, message_id, short_content):
        self.short_content_updates.append((message_id, short_content))

    async def save_exchange(self, thread_id, user_input, assistant_response):
        pass

    async def clear_thread(self, thread_id):
        pass

    async def update(self, message_id, content):
        pass

    async def delete(self, message_id):
        pass

    async def delete_from(self, thread_id, message_id):
        pass

    async def delete_after(self, thread_id, message_id):
        pass

    async def get_versions(self, message_id):
        return []

    async def update_branch(self, message_id, branch_group, branch_index, is_active):
        pass

    async def get_last_bot_message(self, thread_id):
        return None

    async def switch_version(self, branch_group, target_version_id):
        pass

    async def save_branch(
        self,
        thread_id,
        role,
        content,
        branch_group,
        branch_index,
        timestamp=None,
        generation_status: str = "complete",
    ):
        return await self.save(
            thread_id,
            role,
            content,
            branch_group=branch_group,
            branch_index=branch_index,
            is_active=True,
            timestamp=timestamp,
        )

    async def deactivate_branch_group(self, branch_group, thread_id):
        pass


class FakeThreadRepo:
    def __init__(self):
        self.summaries: dict[int, str] = {}

    async def create(self, bot_id, name="", persona_id=None):
        return 1

    async def get(self, thread_id):
        return None

    async def list_for_bot(self, bot_id):
        return []

    async def list_recent(self, limit=20):
        return []

    async def rename(self, thread_id, name):
        pass

    async def delete(self, thread_id):
        pass

    async def set_persona(self, thread_id, persona_id):
        pass

    async def find_by_bot_and_persona(self, bot_id, persona_id):
        return None

    def update_summary(self, thread_id, summary):
        self.summaries[thread_id] = summary


class FakeKnowledgeRepo:
    def __init__(self):
        self._entries: dict[int, list[str]] = {}

    async def search(self, bot_id, query, top_k=3):
        return []

    async def add(self, command):
        pass

    async def delete(self, bot_id, entry_id):
        pass

    async def list_entries(self, bot_id):
        return []

    async def search_with_scores(self, bot_id, query, top_k=5):
        return []

    async def update(self, bot_id, entry_id, content):
        pass


class FakeOrchestrator:
    def __init__(self, response=""):
        self.response = response

    async def generate(self, request):
        return self.response

    async def generate_stream(self, request):
        from app.infrastructure.llm import LLMChunk

        for chunk in self.response:
            yield LLMChunk(content=chunk)


# ── Tests: MessageSummarizer ───────────────────────────────────────────


class TestMessageSummarizer:
    async def test_summarize_message_calls_llm_with_correct_prompt(self):
        llm = FakeLLM("Краткое резюме сообщения.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        await summarizer.summarize_message(
            1, "Очень длинное сообщение, которое нужно суммаризировать. " * 10
        )

        assert len(llm.calls) == 1
        call = llm.calls[0]
        assert call["max_tokens"] == 256  # default from Settings
        assert "system" in [m["role"] for m in call["messages"]]
        assert "user" in [m["role"] for m in call["messages"]]

    async def test_summarize_message_updates_repo(self):
        llm = FakeLLM("Кратко.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        await summarizer.summarize_message(1, "Достаточно длинное сообщение для проверки. " * 10)

        assert len(msgs.short_content_updates) == 1
        assert msgs.short_content_updates[0] == (1, "Кратко.")

    async def test_summarize_skips_short_messages(self):
        """Messages shorter than summarize_min_length should be skipped."""
        llm = FakeLLM("Ответ")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        await summarizer.summarize_message(1, "Коротко.")

        assert len(llm.calls) == 0  # should not call LLM
        assert len(msgs.short_content_updates) == 0

    async def test_summarize_skips_empty_content(self):
        llm = FakeLLM("Ответ")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        result = await summarizer.summarize_message(1, "")
        assert result is None
        assert len(llm.calls) == 0


# ── Tests: Thread Summary ─────────────────────────────────────────────


class TestThreadSummary:
    async def test_summarize_thread_recent_collects_short_content(self):
        llm = FakeLLM("Сюжет: персонажи встретились и обсудили планы.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        recent = [
            MessageDTO(role="user", content="Привет!", short_content="Приветствие"),
            MessageDTO(role="assistant", content="Здравствуй!", short_content="Ответ"),
        ]

        thread_repo = FakeThreadRepo()
        result = await summarizer.summarize_thread_recent(
            1,
            recent,
            on_summary_ready=lambda tid, s: thread_repo.update_summary(tid, s),
        )

        assert result == "Сюжет: персонажи встретились и обсудили планы."
        assert thread_repo.summaries.get(1) == "Сюжет: персонажи встретились и обсудили планы."

    async def test_summarize_thread_uses_full_content_when_no_short(self):
        llm = FakeLLM("Общий сюжет.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        recent = [
            MessageDTO(role="user", content="Первое сообщение пользователя", short_content=None),
            MessageDTO(role="assistant", content="Ответ ассистента", short_content=None),
        ]

        await summarizer.summarize_thread_recent(1, recent)
        # Check that full content was used (truncated to 500 chars)
        # messages[0] = system prompt, messages[1] = user message with history
        call = llm.calls[0]
        user_msg = call["messages"][1]["content"]
        assert "Первое сообщение пользователя" in user_msg

    async def test_summarize_thread_empty_messages(self):
        llm = FakeLLM("Ответ")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        result = await summarizer.summarize_thread_recent(1, [])
        assert result is None
        assert len(llm.calls) == 0


# ── Tests: ChatService summarization integration ──────────────────────


class TestChatServiceSummarization:
    async def test_run_summarization_skips_when_disabled(self):
        """When summarize_enabled=False, run_summarization should not call LLM."""
        FakeLLM("Fake")
        fast_llm = FakeLLM("FastFake")
        msgs = FakeMessageRepo()
        bots = FakeBotRepo()
        orch = FakeOrchestrator("Hello!")
        knowledge = FakeKnowledgeRepo()

        # Disable summarization BEFORE constructing the service — settings
        # are now injected once at construction (K3 fix), so this is the
        # correct way to test env-driven behaviour.
        os.environ["SUMMARIZE_ENABLED"] = "false"

        summarizer = MessageSummarizer(fast_llm, msgs)
        service = ChatService(bots, msgs, knowledge, orch, summarizer=summarizer)

        # Add messages that need summarization
        await msgs.save(1, "user", "Длинное сообщение, которое бы суммаризировали." * 10)
        await msgs.save(1, "assistant", "Длинный ответ ассистента с важной информацией." * 10)  # noqa: RUF001

        await service.run_summarization(1)

        # Should not have called fast LLM
        assert len(fast_llm.calls) == 0

        # Cleanup
        os.environ.pop("SUMMARIZE_ENABLED", None)

    async def test_run_summarization_summarizes_messages_without_short(self):
        """Messages without short_content should get summarized."""
        fast_llm = FakeLLM("Суммаризация.")
        msgs = FakeMessageRepo()
        bots = FakeBotRepo()
        orch = FakeOrchestrator("Hi!")
        knowledge = FakeKnowledgeRepo()

        # Enable summarization BEFORE constructing the service (K3 fix).
        os.environ["SUMMARIZE_ENABLED"] = "true"

        summarizer = MessageSummarizer(fast_llm, msgs)
        service = ChatService(bots, msgs, knowledge, orch, summarizer=summarizer)

        await msgs.save(1, "user", "Достаточно длинное сообщение для проверки. " * 10)

        await service.run_summarization(1)

        # Should have called fast LLM
        assert len(fast_llm.calls) >= 1
        assert len(msgs.short_content_updates) >= 1

        os.environ.pop("SUMMARIZE_ENABLED", None)

    async def test_run_summarization_skips_already_summarized(self):
        """Messages with existing short_content should not be re-summarized."""
        fast_llm = FakeLLM("Суммаризация.")
        msgs = FakeMessageRepo()
        bots = FakeBotRepo()
        orch = FakeOrchestrator("Hi!")
        knowledge = FakeKnowledgeRepo()

        summarizer = MessageSummarizer(fast_llm, msgs)
        service = ChatService(bots, msgs, knowledge, orch, summarizer=summarizer)

        # Save with short_content already set
        await msgs.save(
            1, "user", "Достаточно длинное... " * 10, short_content="Уже есть суммаризация"
        )

        os.environ["SUMMARIZE_ENABLED"] = "true"

        await service.run_summarization(1)

        assert len(fast_llm.calls) == 0
        assert len(msgs.short_content_updates) == 0

        os.environ.pop("SUMMARIZE_ENABLED", None)

    async def test_run_summarization_updates_thread_summary_on_interval(self):
        """When user_msgs_count in the last 20 messages is a multiple of
        ``thread_summary_interval=10``, ``_update_thread_summary`` must run
        and write the summary into ``threads.update_summary``.

        Regression: the modulo check was performed against the narrow
        ``summarize_recent_limit=10`` window (which always holds 0-5 user
        messages), so the modulo never fired and threads ended up with
        permanently NULL summaries.
        """
        fast_llm = FakeLLM("Суммаризация одного сообщения для треда целиком.")
        msgs = FakeMessageRepo()
        bots = FakeBotRepo()
        orch = FakeOrchestrator("Hi!")
        knowledge = FakeKnowledgeRepo()
        threads = FakeThreadRepo()

        os.environ["SUMMARIZE_ENABLED"] = "true"
        os.environ["THREAD_SUMMARY_ENABLED"] = "true"
        os.environ["THREAD_SUMMARY_INTERVAL"] = "10"

        # Build a thread with 20 messages — 10 user + 10 assistant.
        for i in range(10):
            await msgs.save(1, "user", f"Длинное user-сообщение номер {i}. " * 10)
            await msgs.save(1, "assistant", f"Длинный assistant-ответ номер {i}. " * 10)

        summarizer = MessageSummarizer(fast_llm, msgs)
        service = ChatService(bots, msgs, knowledge, orch, summarizer=summarizer, threads=threads)

        await service.run_summarization(1)

        # Thread summary must be written when 10 user msgs fit in the window.
        assert 1 in threads.summaries, (
            f"Thread summary was never written; intervals seen: {threads.summaries}"
        )

        os.environ.pop("SUMMARIZE_ENABLED", None)
        os.environ.pop("THREAD_SUMMARY_ENABLED", None)
        os.environ.pop("THREAD_SUMMARY_INTERVAL", None)

    async def test_run_summarization_uses_wide_window_for_thread_summary(self):
        """The thread-summary interval check must sample a window wide
        enough to actually hit multiples of ``thread_summary_interval``.

        Regression: ``run_summarization`` was sampling the same narrow
        ``summarize_recent_limit=10`` window used for short-content
        generation. With alternating user/assistant messages that window
        only ever contains 0-5 user messages, so ``user_msgs_count %
        thread_summary_interval == 0`` never held and thread summaries
        stayed NULL forever.
        """
        fast_llm = FakeLLM(".")
        msgs = FakeMessageRepo()
        bots = FakeBotRepo()
        orch = FakeOrchestrator("Hi!")
        knowledge = FakeKnowledgeRepo()
        threads = FakeThreadRepo()

        os.environ["SUMMARIZE_ENABLED"] = "true"
        os.environ["THREAD_SUMMARY_ENABLED"] = "true"
        os.environ["THREAD_SUMMARY_INTERVAL"] = "10"

        summarizer = MessageSummarizer(fast_llm, msgs)
        service = ChatService(bots, msgs, knowledge, orch, summarizer=summarizer, threads=threads)

        await service.run_summarization(1)

        # We expect at least one ``list_for_thread`` call with a window
        # wide enough that a multiple of 10 user messages can actually
        # appear in it. 20 covers the smallest case (10 user + 10 asst).
        wide_calls = [
            limit
            for (_tid, limit) in msgs.list_for_thread_calls
            if limit is not None and limit >= 20
        ]
        assert wide_calls, (
            f"run_summarization never sampled a wide-enough window; "
            f"observed limits: {msgs.list_for_thread_calls}"
        )

        os.environ.pop("SUMMARIZE_ENABLED", None)
        os.environ.pop("THREAD_SUMMARY_ENABLED", None)
        os.environ.pop("THREAD_SUMMARY_INTERVAL", None)

    async def test_run_summarization_skips_thread_summary_off_interval(self):
        """When user_msgs_count in the last 20 messages is NOT a multiple
        of ``thread_summary_interval``, ``_update_thread_summary`` must NOT run.
        """
        fast_llm = FakeLLM("Суммаризация одного сообщения.")
        msgs = FakeMessageRepo()
        bots = FakeBotRepo()
        orch = FakeOrchestrator("Hi!")
        knowledge = FakeKnowledgeRepo()
        threads = FakeThreadRepo()

        os.environ["SUMMARIZE_ENABLED"] = "true"
        os.environ["THREAD_SUMMARY_ENABLED"] = "true"
        os.environ["THREAD_SUMMARY_INTERVAL"] = "10"

        # 6 user + 6 assistant = 12 messages, 6 user msgs — not a multiple of 10.
        for i in range(6):
            await msgs.save(1, "user", f"User-сообщение номер {i}. " * 10)
            await msgs.save(1, "assistant", f"Assistant-ответ номер {i}. " * 10)

        summarizer = MessageSummarizer(fast_llm, msgs)
        service = ChatService(bots, msgs, knowledge, orch, summarizer=summarizer, threads=threads)

        await service.run_summarization(1)

        assert threads.summaries == {}, (
            f"Thread summary was unexpectedly written: {threads.summaries}"
        )

        os.environ.pop("SUMMARIZE_ENABLED", None)
        os.environ.pop("THREAD_SUMMARY_ENABLED", None)
        os.environ.pop("THREAD_SUMMARY_INTERVAL", None)


# ── Tests: Settings ────────────────────────────────────────────────────


class TestSettings:
    def test_fast_model_default(self, monkeypatch):
        """Default fast_model should be gpt-4o-mini when no env override.

        Uses ``monkeypatch.delenv`` AND ``_env_file=None`` because
        pydantic-settings reads from the on-disk .env file in addition
        to ``os.environ`` — delenv alone is not enough to test the
        dataclass-style default.
        """
        monkeypatch.delenv("FAST_MODEL", raising=False)
        settings = Settings(llm_api_key="sk-test", _env_file=None)
        assert settings.fast_model == "openai/gpt-4o-mini"

    def test_fast_model_from_env(self, monkeypatch):
        monkeypatch.setenv("FAST_MODEL", "anthropic/claude-haiku")
        settings = Settings.from_env()
        assert settings.fast_model == "anthropic/claude-haiku"

    def test_summarize_settings_defaults(self, monkeypatch):
        # Pin the ambient environment to defaults so this test is
        # independent of the local .env file (pydantic-settings
        # otherwise reads it on every construction).
        for k in (
            "SUMMARIZE_ENABLED",
            "SUMMARIZE_MAX_TOKENS",
            "SUMMARIZE_MIN_LENGTH",
            "THREAD_SUMMARY_ENABLED",
            "THREAD_SUMMARY_INTERVAL",
        ):
            monkeypatch.delenv(k, raising=False)
        settings = Settings(llm_api_key="sk-test")
        assert settings.summarize_enabled is True
        assert settings.summarize_max_tokens == 256
        assert settings.summarize_min_length == 100
        assert settings.thread_summary_enabled is True
        assert settings.thread_summary_interval == 10

    def test_summarize_settings_from_env(self):
        os.environ["SUMMARIZE_MAX_TOKENS"] = "128"
        os.environ["SUMMARIZE_MIN_LENGTH"] = "50"
        os.environ["SUMMARIZE_ENABLED"] = "false"
        os.environ["THREAD_SUMMARY_INTERVAL"] = "5"

        settings = Settings.from_env()
        assert settings.summarize_max_tokens == 128
        assert settings.summarize_min_length == 50
        assert settings.summarize_enabled is False
        assert settings.thread_summary_interval == 5

        for key in [
            "SUMMARIZE_MAX_TOKENS",
            "SUMMARIZE_MIN_LENGTH",
            "SUMMARIZE_ENABLED",
            "THREAD_SUMMARY_INTERVAL",
        ]:
            os.environ.pop(key, None)


# ── Tests: Batch Settings ─────────────────────────────────────────────


class TestBatchSettings:
    def test_batch_settings_defaults(self):
        """Batch summarization should be enabled by default with concurrency 3."""
        settings = Settings(llm_api_key="sk-test")
        assert settings.summarize_batch_enabled is True
        assert settings.summarize_batch_size == 3

    def test_batch_settings_from_env(self):
        os.environ["SUMMARIZE_BATCH_ENABLED"] = "false"
        os.environ["SUMMARIZE_BATCH_SIZE"] = "5"

        settings = Settings.from_env()
        assert settings.summarize_batch_enabled is False
        assert settings.summarize_batch_size == 5

        os.environ.pop("SUMMARIZE_BATCH_ENABLED", None)
        os.environ.pop("SUMMARIZE_BATCH_SIZE", None)


# ── Tests: Async LLM ──────────────────────────────────────────────────


class FakeAsyncLLM:
    """LLMPort fake for testing batch summarization."""

    def __init__(self, response: str = "Async canned response."):
        self.response = response
        self.calls: list[dict] = []
        self.call_count = 0

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(
            {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }
        )
        self.call_count += 1
        return self.response


class TestLLMPortFake:
    def test_fake_llm_records_calls(self):
        """FakeAsyncLLM should record call parameters."""
        import asyncio

        llm = FakeAsyncLLM("Test response")
        result = asyncio.run(
            llm.generate_response(
                [{"role": "user", "content": "test"}],
                temperature=0.3,
                max_tokens=100,
            )
        )
        assert result == "Test response"
        assert len(llm.calls) == 1
        assert llm.calls[0]["temperature"] == 0.3
        assert llm.calls[0]["max_tokens"] == 100


# ── Tests: MessageSummarizer.batch_summarize ──────────────────────────


class TestBatchSummarize:
    def test_batch_summarize_calls_llm_for_each_message(self):
        """batch_summarize should call async LLM for each valid message."""
        import asyncio

        llm = FakeAsyncLLM("Суммаризация.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        items = [
            (1, "Очень длинное сообщение первое, которое нужно суммаризировать. " * 5),
            (2, "Очень длинное сообщение второе, которое тоже нужно обработать. " * 5),
        ]

        result = asyncio.run(summarizer.batch_summarize(items, max_concurrent=2))

        assert len(llm.calls) == 2
        assert result[1] == "Суммаризация."
        assert result[2] == "Суммаризация."

    def test_batch_summarize_skips_short_messages(self):
        """Messages shorter than summarize_min_length should be skipped."""
        import asyncio

        llm = FakeAsyncLLM("Суммаризация.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        items = [
            (1, "Коротко."),  # too short
            (2, "Очень длинное сообщение для проверки суммаризации. " * 5),
        ]

        result = asyncio.run(summarizer.batch_summarize(items, max_concurrent=2))

        assert len(llm.calls) == 1  # only the long message
        assert 1 not in result  # short message was skipped
        assert result[2] == "Суммаризация."

    def test_batch_summarize_updates_repo(self):
        """batch_summarize should update short_content for each summarized message."""
        import asyncio

        llm = FakeAsyncLLM("Результат.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        items = [
            (10, "Достаточно длинное сообщение для проверки batch суммаризации. " * 5),
        ]

        asyncio.run(summarizer.batch_summarize(items, max_concurrent=1))

        assert len(msgs.short_content_updates) == 1
        assert msgs.short_content_updates[0] == (10, "Результат.")

    def test_batch_summarize_respects_max_concurrent(self):
        """max_concurrent should limit parallel requests."""
        import asyncio
        import time

        call_times = []

        class SlowFakeLLM(FakeAsyncLLM):
            async def generate_response(self, messages, temperature=None, max_tokens=None):
                call_times.append(("start", time.monotonic()))
                await asyncio.sleep(0.1)
                call_times.append(("end", time.monotonic()))
                return await super().generate_response(messages, temperature, max_tokens)

        llm = SlowFakeLLM("Ответ.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        items = [
            (i, f"Длинное сообщение номер {i} для проверки параллельности. " * 5) for i in range(4)
        ]

        asyncio.run(summarizer.batch_summarize(items, max_concurrent=2))

        # All 4 messages should be summarized
        assert len(llm.calls) == 4

    def test_batch_summarize_empty_items(self):
        """batch_summarize with empty items should return empty dict."""
        import asyncio

        llm = FakeAsyncLLM("Ответ.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        result = asyncio.run(summarizer.batch_summarize([], max_concurrent=3))

        assert result == {}
        assert len(llm.calls) == 0

    def test_batch_summarize_handles_errors_gracefully(self):
        """batch_summarize should return None for failed messages."""
        import asyncio

        class FailingLLM(FakeAsyncLLM):
            async def generate_response(self, messages, temperature=None, max_tokens=None):
                raise RuntimeError("API error")

        llm = FailingLLM("Ответ.")
        msgs = FakeMessageRepo()
        summarizer = MessageSummarizer(llm, msgs)

        items = [
            (1, "Длинное сообщение которое не получится суммаризировать. " * 5),
        ]

        result = asyncio.run(summarizer.batch_summarize(items, max_concurrent=1))

        assert result[1] is None
        assert len(msgs.short_content_updates) == 0  # no update on failure


# ── Tests: ChatService batch integration ──────────────────────────────


class FakeDualLLM:
    """LLM fake that implements both sync and async methods."""

    def __init__(self, response: str = "Dual response."):
        self.response = response
        self.calls: list[dict] = []

    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append(
            {"messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        )
        return self.response

    def generate_response_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ):
        from app.infrastructure.llm import LLMChunk

        yield LLMChunk(content=self.response)


class TestChatServiceBatchIntegration:
    async def test_run_summarization_uses_batch_when_enabled(self):
        """When summarize_batch_enabled=True, run_summarization should use batch_summarize."""
        import os

        llm = FakeDualLLM("Суммаризация.")
        msgs = FakeMessageRepo()
        bots = FakeBotRepo()
        orch = FakeOrchestrator("Hi!")
        knowledge = FakeKnowledgeRepo()

        summarizer = MessageSummarizer(llm, msgs)
        service = ChatService(bots, msgs, knowledge, orch, summarizer=summarizer)

        # Add messages that need summarization
        await msgs.save(1, "user", "Длинное сообщение пользователя для проверки batch. " * 10)
        await msgs.save(1, "assistant", "Длинный ответ ассистента для проверки batch. " * 10)

        # Enable batch summarization
        os.environ["SUMMARIZE_ENABLED"] = "true"
        os.environ["SUMMARIZE_BATCH_ENABLED"] = "true"
        os.environ["SUMMARIZE_BATCH_SIZE"] = "2"

        await service.run_summarization(1)

        # Should have summarized both recent messages via the LLMPort contract.
        assert len(llm.calls) >= 1
        assert len(msgs.short_content_updates) >= 1

        # Cleanup
        for key in ["SUMMARIZE_ENABLED", "SUMMARIZE_BATCH_ENABLED", "SUMMARIZE_BATCH_SIZE"]:
            os.environ.pop(key, None)

    async def test_run_summarization_uses_sync_when_batch_disabled(self):
        """When summarize_batch_enabled=False, run_summarization should use sequential summarize_message."""
        import os

        llm = FakeDualLLM("Суммаризация.")
        msgs = FakeMessageRepo()
        bots = FakeBotRepo()
        orch = FakeOrchestrator("Hi!")
        knowledge = FakeKnowledgeRepo()

        summarizer = MessageSummarizer(llm, msgs)
        service = ChatService(bots, msgs, knowledge, orch, summarizer=summarizer)

        # Add messages that need summarization
        await msgs.save(1, "user", "Длинное сообщение пользователя для проверки sync. " * 10)

        # Disable batch summarization
        os.environ["SUMMARIZE_ENABLED"] = "true"
        os.environ["SUMMARIZE_BATCH_ENABLED"] = "false"

        await service.run_summarization(1)

        # Should have summarized the recent message via the same LLMPort contract.
        assert len(llm.calls) >= 1

        # Cleanup
        for key in ["SUMMARIZE_ENABLED", "SUMMARIZE_BATCH_ENABLED"]:
            os.environ.pop(key, None)


# ── Tests: list_for_thread with versions ──────────────────────────────


class TestListForThreadVersions:
    async def test_versions_empty_for_regular_message(self):
        """A regular message without branch_group should have empty versions."""
        msgs = FakeMessageRepo()
        await msgs.save(1, "user", "Hello")
        await msgs.save(1, "assistant", "Hi there")

        result = await msgs.list_for_thread(1)
        for m in result:
            assert m.versions == []

    async def test_versions_populated_for_branched_message(self):
        """Message with branch_group should include its versions."""
        msgs = FakeMessageRepo()
        # Original message
        await msgs.save(
            1,
            "assistant",
            "First version",
            branch_group="branch-1",
            branch_index=0,
            is_active=False,
        )
        # Active version
        await msgs.save(
            1,
            "assistant",
            "Second version",
            branch_group="branch-1",
            branch_index=1,
            is_active=True,
        )

        result = await msgs.list_for_thread(1)
        active_msgs = [m for m in result if m.branch_group == "branch-1"]
        assert len(active_msgs) == 1
        assert active_msgs[0].content == "Second version"
        assert len(active_msgs[0].versions) == 2
        assert active_msgs[0].versions[0].content == "First version"
        assert active_msgs[0].versions[1].content == "Second version"


# ── Helpers ─────────────────────────────────────────────────────────────


class FakeBot:
    """Minimal bot-like object for repo returns."""

    def __init__(
        self,
        bot_id=1,
        name="TestBot",
        personality="Friendly",
        first_message="Hello!",
        scenario="",
        bot_type="rp",
    ):
        self.id = bot_id
        self.name = name
        self.personality = personality
        self.first_message = first_message
        self.scenario = scenario
        self.bot_type = bot_type
        self.description = ""
        self.avatar_path = None
        self.categories = "[]"
        self.thread_count = 0


class FakeBotRepo:
    def __init__(self):
        self._bots = {1: FakeBot()}

    async def create(self, *args, **kwargs):
        return 1

    async def get(self, bot_id):
        return self._bots.get(bot_id)

    async def list(self):
        return list(self._bots.values())

    async def delete(self, bot_id):
        pass

    async def update(self, *args, **kwargs):
        pass

    async def get_with_thread_counts(self):
        return [(b, 0) for b in self._bots.values()]
