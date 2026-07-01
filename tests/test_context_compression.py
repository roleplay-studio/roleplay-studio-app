"""Tests for context compression — replacing old messages with short_content.

Focus areas:
  - _build_request() compresses old messages when threshold exceeded
  - No compression below threshold or when disabled
  - Graceful degradation (messages without short_content stay full)
  - context_compressed flag propagation
  - Orchestrator system hint when context_compressed=True
  - keep_recent preserves last N messages at full detail
"""

from __future__ import annotations

import os
from unittest.mock import patch

from app.application.dto import MessageDTO, SendMessageCommand
from app.application.services import ChatService
from app.infrastructure.config import Settings
from app.infrastructure.orchestration.langgraph_orchestrator import (
    LangGraphConversationOrchestrator,
)

# ── Reuse fakes from test_chat_generation ──────────────────────────
from tests.test_chat_generation import (
    BranchMessageRepo as _BaseBranchMessageRepo,
)
from tests.test_chat_generation import (
    FakeBotRepo,
    FakeKnowledgeRepo,
    FakeLLM,
    FakeOrchestrator,
    _make_bot,
)


class BranchMessageRepo(_BaseBranchMessageRepo):
    """Extended with update_short_content for compression tests."""

    def update_short_content(self, message_id: int, short_content: str) -> None:
        for e in self._msgs:
            if e.msg.id == message_id:
                e.msg.short_content = short_content
                break


# ── Helpers ────────────────────────────────────────────────────────


async def _seed_messages(
    repo: BranchMessageRepo, thread_id: int, count: int, *, with_short_content: bool = True
):
    """Seed `count` alternating user/assistant messages into repo."""
    for i in range(count):
        role = "user" if i % 2 == 0 else "assistant"
        content = f"Message {i}: {'Hello world' * 10}"  # >100 chars to be above min_length
        short = f"msg{i} summary" if with_short_content else None
        msg_id = await repo.save(thread_id, role, content)
        if short and msg_id:
            repo.update_short_content(msg_id, short)


def _make_service(
    bots: FakeBotRepo | None = None,
    msgs: BranchMessageRepo | None = None,
    orch: FakeOrchestrator | None = None,
    llm: FakeLLM | None = None,
    settings: Settings | None = None,
) -> ChatService:
    """Construct a ChatService.

    After the K3 fix settings are injected at construction. Pass an
    explicit ``settings`` to test env-driven behaviour; otherwise the
    service reads the ambient environment via ``Settings.from_env()``.
    """
    bots = bots or FakeBotRepo()
    msgs = msgs or BranchMessageRepo()
    orch = orch or FakeOrchestrator()
    llm = llm or FakeLLM()
    return ChatService(bots, msgs, FakeKnowledgeRepo(), orch, settings=settings, llm=llm)


def _service_with_overrides(
    bots: FakeBotRepo,
    msgs: BranchMessageRepo,
    **overrides: object,
) -> ChatService:
    """Compose the env-override + service-construction steps.

    After the K3 fix, settings are no longer re-read on every request
    (K3 in docs/review.md). To test env-driven behaviour we have to
    build a fresh ``Settings`` *inside* the env-override context — this
    helper does that in one line so the test bodies stay readable.
    """
    with _env_override(**overrides):
        return _make_service(bots=bots, msgs=msgs, settings=Settings.from_env())


def _env_override(**kwargs):
    """Context manager to override env vars for the duration of the block.

    Tests that want to exercise env-driven behaviour (e.g. context
    compression) should pair this with ``_service_with_overrides`` so
    the service picks up the overridden environment at construction.
    """
    env_map = {
        "context_compression_enabled": "CONTEXT_COMPRESSION_ENABLED",
        "context_compression_threshold": "CONTEXT_COMPRESSION_THRESHOLD",
        "context_compression_keep_recent": "CONTEXT_COMPRESSION_KEEP_RECENT",
    }
    env = {}
    for key, val in kwargs.items():
        env_key = env_map.get(key)
        if env_key:
            env[env_key] = str(val).lower() if isinstance(val, bool) else str(val)
    return patch.dict(os.environ, env)


# ══════════════════════════════════════════════════════════════════════
#  Context compression in _build_request()
# ══════════════════════════════════════════════════════════════════════


class TestContextCompression:
    """Tests for the context compression logic in ChatService._build_request()."""

    async def _build(self, service: ChatService, thread_id: int = 1, bot_id: int = 1):
        """Helper to call _build_request with a standard command."""
        cmd = SendMessageCommand(thread_id=thread_id, bot_id=bot_id, user_input="latest user msg")
        return await service._build_request(cmd)

    # ── Compression triggers when threshold exceeded ────────────────

    async def test_compresses_old_messages_above_threshold(self):
        """When message count > threshold, old messages should use short_content."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        await _seed_messages(msgs, thread_id=1, count=60, with_short_content=True)

        # Settings must be constructed inside the env-override block — see K3 fix.
        with _env_override(
            context_compression_enabled=True,
            context_compression_threshold=50,
            context_compression_keep_recent=20,
        ):
            service = _make_service(bots=bots, msgs=msgs, settings=Settings.from_env())
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        # Old messages (before cutoff) should have short_content as content
        old_msgs = req.history[: len(req.history) - 20]
        for msg in old_msgs:
            assert "summary" in msg.content, (
                f"Old message {msg.id} should be compressed, got: {msg.content[:50]}"
            )

        # Recent messages should keep full content
        recent_msgs = req.history[-20:]
        for msg in recent_msgs:
            assert "summary" not in msg.content, (
                f"Recent message {msg.id} should be full, got: {msg.content[:50]}"
            )

    async def test_sets_context_compressed_flag(self):
        """context_compressed should be True when compression was applied."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        await _seed_messages(msgs, thread_id=1, count=60, with_short_content=True)

        # Settings must be constructed inside the env-override block — see K3 fix.
        with _env_override(
            context_compression_enabled=True,
            context_compression_threshold=50,
            context_compression_keep_recent=20,
        ):
            service = _make_service(bots=bots, msgs=msgs, settings=Settings.from_env())
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        assert req.context_compressed is True

    # ── No compression below threshold ─────────────────────────────

    async def test_no_compression_below_threshold(self):
        """Messages stay full when count <= threshold."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        await _seed_messages(msgs, thread_id=1, count=30, with_short_content=True)

        service = _make_service(bots=bots, msgs=msgs)

        with _env_override(
            context_compression_enabled=True,
            context_compression_threshold=50,
            context_compression_keep_recent=20,
        ):
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        # All messages should keep full content
        for msg in req.history:
            assert "summary" not in msg.content, f"Message {msg.id} should not be compressed"

        assert req.context_compressed is False

    # ── No compression when disabled ────────────────────────────────

    async def test_no_compression_when_disabled(self):
        """Messages stay full when context_compression_enabled=False."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        await _seed_messages(msgs, thread_id=1, count=60, with_short_content=True)

        # After the K3 fix, settings are injected once at construction.
        # The ``_env_override`` + ``_make_service`` composition must happen
        # in the right order — see ``_service_with_overrides``.
        with _env_override(
            context_compression_enabled=False,
            context_compression_threshold=50,
            context_compression_keep_recent=20,
        ):
            service = _make_service(bots=bots, msgs=msgs, settings=Settings.from_env())
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        for msg in req.history:
            assert "summary" not in msg.content

        assert req.context_compressed is False

    # ── Graceful degradation: no short_content ──────────────────────

    async def test_graceful_when_no_short_content(self):
        """Messages without short_content stay at full content even when compression is on."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        await _seed_messages(msgs, thread_id=1, count=60, with_short_content=False)

        service = _make_service(bots=bots, msgs=msgs)

        with _env_override(
            context_compression_enabled=True,
            context_compression_threshold=50,
            context_compression_keep_recent=20,
        ):
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        # No messages should be compressed (none have short_content)
        for msg in req.history:
            assert "summary" not in msg.content

        assert req.context_compressed is False

    async def test_partial_compression(self):
        """Only messages WITH short_content get compressed; others stay full."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()

        # Seed 60 messages — only even-indexed ones get short_content
        for i in range(60):
            role = "user" if i % 2 == 0 else "assistant"
            content = f"Message {i}: {'Hello world' * 10}"
            msg_id = await msgs.save(1, role, content)
            if i % 2 == 0 and msg_id:
                msgs.update_short_content(msg_id, f"summary {i}")

        # Settings must be constructed inside the env-override block — see K3 fix.
        with _env_override(
            context_compression_enabled=True,
            context_compression_threshold=50,
            context_compression_keep_recent=20,
        ):
            service = _make_service(bots=bots, msgs=msgs, settings=Settings.from_env())
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        # Some old messages compressed, some not — but flag should be True
        assert req.context_compressed is True

    # ── keep_recent boundary ────────────────────────────────────────

    async def test_keep_recent_preserves_exact_count(self):
        """Exactly `keep_recent` messages should stay at full detail."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        await _seed_messages(msgs, thread_id=1, count=60, with_short_content=True)

        # Settings must be constructed inside the env-override block —
        # see K3 fix in docs/review.md.
        with _env_override(
            context_compression_enabled=True,
            context_compression_threshold=50,
            context_compression_keep_recent=10,
        ):
            service = _make_service(bots=bots, msgs=msgs, settings=Settings.from_env())
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        compressed = sum(1 for m in req.history if "summary" in m.content)
        full = sum(1 for m in req.history if "summary" not in m.content)

        # Last 10 should be full, rest should be compressed
        assert full == 10
        assert compressed == len(req.history) - 10

    async def test_threshold_at_boundary_no_compression(self):
        """No compression when message count == threshold (not exceeding)."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        await _seed_messages(msgs, thread_id=1, count=50, with_short_content=True)

        service = _make_service(bots=bots, msgs=msgs)

        with _env_override(
            context_compression_enabled=True,
            context_compression_threshold=50,
            context_compression_keep_recent=20,
        ):
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        assert req.context_compressed is False

    async def test_threshold_one_over_triggers_compression(self):
        """Compression triggers when history count exceeds threshold."""
        bots = FakeBotRepo()
        bot_id = await _make_bot(bots)
        msgs = BranchMessageRepo()
        # Seed 52 — last user msg gets excluded from history, leaving 51 > 50
        await _seed_messages(msgs, thread_id=1, count=52, with_short_content=True)

        # Settings must be constructed inside the env-override block — see K3 fix.
        with _env_override(
            context_compression_enabled=True,
            context_compression_threshold=50,
            context_compression_keep_recent=20,
        ):
            service = _make_service(bots=bots, msgs=msgs, settings=Settings.from_env())
            req = await self._build(service, thread_id=1, bot_id=bot_id)

        assert req.context_compressed is True


# ══════════════════════════════════════════════════════════════════════
#  Orchestrator system hint
# ══════════════════════════════════════════════════════════════════════


class TestOrchestratorCompressionHint:
    """Tests for the system hint injected when context_compressed=True."""

    def _build_messages(self, context_compressed: bool = False):
        """Build LLM messages via orchestrator with a mock request."""
        from unittest.mock import MagicMock

        from app.application.dto import ConversationRequest

        request = ConversationRequest(
            thread_id=1,
            bot_id=1,
            user_input="hello",
            bot_name="TestBot",
            bot_personality="Friendly",
            bot_scenario="Test scenario",
            first_message="",
            history=[
                MessageDTO(role="user", content="hi", created_at=None),
                MessageDTO(role="assistant", content="hello!", created_at=None),
            ],
            untrusted_context=[],
            context_compressed=context_compressed,
        )

        llm = MagicMock()
        orch = LangGraphConversationOrchestrator(llm)
        return orch._build_all_messages(request)

    def test_hint_added_when_compressed(self):
        """System hint should appear when context_compressed=True."""
        messages = self._build_messages(context_compressed=True)

        # Find the compression hint
        hint_msgs = [
            m
            for m in messages
            if m["role"] == "system" and "compressed summaries" in m.get("content", "").lower()
        ]
        assert len(hint_msgs) == 1
        assert "brief descriptions" in hint_msgs[0]["content"].lower()

    def test_no_hint_when_not_compressed(self):
        """No compression hint when context_compressed=False."""
        messages = self._build_messages(context_compressed=False)

        hint_msgs = [
            m
            for m in messages
            if m["role"] == "system" and "compressed summaries" in m.get("content", "").lower()
        ]
        assert len(hint_msgs) == 0

    def test_hint_inserted_after_system_prompt(self):
        """The hint should be at position 1 (after main system prompt)."""
        messages = self._build_messages(context_compressed=True)

        # Position 0 = main system prompt, position 1 = compression hint
        assert messages[0]["role"] == "system"
        assert "compressed summaries" in messages[1]["content"].lower()

    def test_hint_does_not_break_history(self):
        """History messages should still be present after the hint."""
        messages = self._build_messages(context_compressed=True)

        # system, hint, user, assistant (history), user (input)
        roles = [m["role"] for m in messages]
        assert "user" in roles
        assert "assistant" in roles


# ══════════════════════════════════════════════════════════════════════
#  Settings integration
# ══════════════════════════════════════════════════════════════════════


class TestCompressionSettings:
    """Tests for context compression settings."""

    def test_default_settings(self):
        """Default values should be sensible."""
        from app.infrastructure.config import Settings

        # Isolate from ambient .env / os.environ: the on-disk ``.env``
        # file (loaded by SettingsConfigDict.env_file) overrides the
        # field defaults whenever CONTEXT_COMPRESSION_* is set there.
        # Tests must see the *defaults*, so strip the variables AND
        # override ``_env_file`` to None for the construction call.
        env_keys = (
            "CONTEXT_COMPRESSION_ENABLED",
            "CONTEXT_COMPRESSION_THRESHOLD",
            "CONTEXT_COMPRESSION_KEEP_RECENT",
        )
        with patch.dict(os.environ, {}, clear=False):
            for k in env_keys:
                os.environ.pop(k, None)
            s = Settings(_env_file=None)
        assert s.context_compression_enabled is True
        assert s.context_compression_threshold == 50
        assert s.context_compression_keep_recent == 20

    def test_settings_from_env(self):
        """Settings should read from environment variables."""
        from app.infrastructure.config import Settings

        env = {
            "CONTEXT_COMPRESSION_ENABLED": "false",
            "CONTEXT_COMPRESSION_THRESHOLD": "100",
            "CONTEXT_COMPRESSION_KEEP_RECENT": "30",
        }
        with patch.dict(os.environ, env):
            s = Settings.from_env()

        assert s.context_compression_enabled is False
        assert s.context_compression_threshold == 100
        assert s.context_compression_keep_recent == 30

    def test_settings_from_env_defaults(self):
        """Missing env vars should fall back to defaults."""
        from app.infrastructure.config import Settings

        # Strip the relevant env vars and override ``_env_file`` to
        # None so the on-disk .env file (if any) cannot leak values
        # into the field defaults.
        env_keys = (
            "CONTEXT_COMPRESSION_ENABLED",
            "CONTEXT_COMPRESSION_THRESHOLD",
            "CONTEXT_COMPRESSION_KEEP_RECENT",
        )
        with patch.dict(os.environ, {}, clear=False):
            for k in env_keys:
                os.environ.pop(k, None)
            s = Settings.from_env() if False else Settings(_env_file=None)

        assert s.context_compression_enabled is True
        assert s.context_compression_threshold == 50
        assert s.context_compression_keep_recent == 20


# ══════════════════════════════════════════════════════════════════════
#  API schema validation
# ══════════════════════════════════════════════════════════════════════


class TestCompressionAPI:
    """Tests for API schema and config endpoint."""

    def test_update_config_schema_accepts_compression_fields(self):
        """UpdateConfigRequest should accept compression fields."""
        from api.schemas import UpdateConfigRequest

        req = UpdateConfigRequest(
            context_compression_enabled=False,
            context_compression_threshold=100,
            context_compression_keep_recent=30,
        )
        assert req.context_compression_enabled is False
        assert req.context_compression_threshold == 100
        assert req.context_compression_keep_recent == 30

    def test_update_config_schema_allows_none(self):
        """Compression fields should be optional (None)."""
        from api.schemas import UpdateConfigRequest

        req = UpdateConfigRequest()
        assert req.context_compression_enabled is None
        assert req.context_compression_threshold is None
        assert req.context_compression_keep_recent is None

    def test_conversation_request_has_context_compressed(self):
        """ConversationRequest should have context_compressed field defaulting to False."""
        from app.application.dto import ConversationRequest

        req = ConversationRequest(
            thread_id=1,
            bot_id=1,
            user_input="hi",
            bot_name="Bot",
            bot_personality="test",
            bot_scenario="test",
            first_message="",
            history=[],
            untrusted_context=[],
        )
        assert req.context_compressed is False

    def test_conversation_request_context_compressed_true(self):
        """context_compressed can be set to True."""
        from app.application.dto import ConversationRequest

        req = ConversationRequest(
            thread_id=1,
            bot_id=1,
            user_input="hi",
            bot_name="Bot",
            bot_personality="test",
            bot_scenario="test",
            first_message="",
            history=[],
            untrusted_context=[],
            context_compressed=True,
        )
        assert req.context_compressed is True
