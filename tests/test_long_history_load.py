"""Tests for the long-history fix: stream_message / regenerate / retry
must load the FULL thread history, not the repository's default
``limit=20``.

Regression: DEBUG1 had 91 active messages in DB but only 20 reached
the LLM because ``ChatService._build_request`` called
``self._messages.list_for_thread(thread_id)`` without an explicit
``limit`` argument, and the real SqlAlchemyMessageRepository defaults
to ``limit=20``. The LLM therefore lost ~78% of the context.

After the fix, ``_build_request`` must pass the configured
``Settings.history_limit`` (default 200) so the real repo returns up
to 200 messages, which then triggers the existing
``context_compression`` branch (>threshold=50) for long threads.
"""

from __future__ import annotations

import os
from unittest.mock import patch

from app.application.dto import SendMessageCommand
from app.application.services import ChatService
from app.infrastructure.config import Settings
from tests.test_chat_generation import (
    FakeBotRepo,
    FakeKnowledgeRepo,
    FakeLLM,
    FakeOrchestrator,
    _make_bot,
)


class _SpyMessageRepo:
    """Message repository that records the ``limit`` it was called with.

    The real SqlAlchemyMessageRepository defaults to ``limit=20`` when
    none is supplied, so the bug only shows up when the caller
    forgets to pass anything. We mirror that behaviour here: an
    unspecified limit quietly caps the result to 20 — the same way
    the real repo would.
    """

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._msgs: list = []
        self._next_id = 1

    async def save(self, thread_id, role, content, **kwargs):
        from types import SimpleNamespace

        from app.application.dto import MessageDTO

        msg_id = self._next_id
        self._next_id += 1
        msg = MessageDTO(id=msg_id, role=role, content=content, **kwargs)
        self._msgs.append(SimpleNamespace(tid=thread_id, msg=msg))
        return msg_id

    async def save_exchange(self, thread_id, user_input, assistant_response):
        await self.save(thread_id, "user", user_input)
        await self.save(thread_id, "assistant", assistant_response)

    async def list_for_thread(self, thread_id, limit: int = 20):
        # Mirror the real repo: omit a limit → silently cap at 20.
        self.calls.append({"thread_id": thread_id, "limit": limit})
        result = [e.msg for e in self._msgs if e.msg.is_active]
        return result[-limit:]

    async def list_all_for_thread(self, thread_id):
        return [e.msg for e in self._msgs]


def _make_service(
    msgs: _SpyMessageRepo | None = None,
    bots: FakeBotRepo | None = None,
    settings: Settings | None = None,
) -> ChatService:
    # Note: ChatService's 4th positional arg is `orchestrator`.
    return ChatService(
        bots=bots or FakeBotRepo(),
        messages=msgs or _SpyMessageRepo(),
        knowledge=FakeKnowledgeRepo(),
        orchestrator=FakeOrchestrator(),
        settings=settings,
        llm=FakeLLM(),
    )


# ══════════════════════════════════════════════════════════════════════
#  The regression: _build_request must request a large enough limit
# ══════════════════════════════════════════════════════════════════════


async def _seed_n(msgs: _SpyMessageRepo, n: int, thread_id: int = 1) -> None:
    """Seed ``n`` user/assistant pairs into the spy repo."""
    for i in range(n):
        role = "user" if i % 2 == 0 else "assistant"
        await msgs.save(thread_id, role, f"msg {i}: {'x' * 50}")


async def test_build_request_loads_all_history_not_just_20():
    """The fatal regression: thread has 91 messages, but the service
    must not be limited to the repo's default of 20.

    We use a SpyMessageRepo whose ``list_for_thread`` mirrors the
    real repo's ``limit=20`` default. If the service forgets to pass
    an explicit limit, this spy will return only the last 20
    messages — and the test will fail by counting ``len(req.history)``.
    """
    bots = FakeBotRepo()
    bot_id = await _make_bot(bots)
    msgs = _SpyMessageRepo()
    await _seed_n(msgs, n=91, thread_id=1)

    service = _make_service(bots=bots, msgs=msgs)

    cmd = SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="hi")
    # Avoid env interference — defaults are fine.
    with patch.dict(os.environ, {}, clear=False):
        req = await service._build_request(cmd)

    # Last user msg is filtered out of history, so 90 not 91.
    assert len(req.history) == 90, (
        f"expected 90 history messages (91 - last user), got {len(req.history)}"
    )
    # And the spy must have been called with the configured limit
    # (Settings.history_limit defaults to 200), not the repo's 20.
    assert msgs.calls[0]["limit"] >= 90


async def test_build_request_with_long_history_triggers_compression():
    """A 91-message thread must trigger context compression once
    history is correctly loaded. Without the fix, len(history) <= 20
    and compression never fires — the LLM sees only the latest 20
    full-detail messages and misses the rest of the conversation.

    We seed 91 messages — all with short_content — and verify that
    ``req.context_compressed`` is True and that the older messages
    are replaced by their short_content in the LLM payload.
    """
    bots = FakeBotRepo()
    bot_id = await _make_bot(bots)
    msgs = _SpyMessageRepo()
    # Seed 91 messages WITH short_content so compression can kick in.
    for i in range(91):
        role = "user" if i % 2 == 0 else "assistant"
        await msgs.save(
            1,
            role,
            f"long content {i}: " + ("a" * 200),
            short_content=f"summary {i}",
        )

    service = _make_service(bots=bots, msgs=msgs)

    cmd = SendMessageCommand(thread_id=1, bot_id=bot_id, user_input="hi")

    # Settings must be constructed inside the env-override block — see K3 fix.
    with patch.dict(
        os.environ,
        {
            "CONTEXT_COMPRESSION_ENABLED": "true",
            "CONTEXT_COMPRESSION_THRESHOLD": "50",
            "CONTEXT_COMPRESSION_KEEP_RECENT": "20",
        },
        clear=False,
    ):
        # Reconstruct the service so it picks up the overridden
        # context-compression settings (K3 freezes settings at
        # construction time).
        service = _make_service(bots=bots, msgs=msgs, settings=Settings.from_env())
        req = await service._build_request(cmd)

    # 91 - 1 last user = 90 history messages.
    assert len(req.history) == 90
    # The flag must be set — at least one old message had short_content
    # and was compressed.
    assert req.context_compressed is True, (
        "long history (90 msgs) with short_content available must trigger "
        f"context_compressed=True, got {req.context_compressed}"
    )
    # First 70 messages (= 90 - 20) should be replaced by short_content.
    # The exact index depends on ordering — just spot-check the oldest.
    oldest = req.history[0]
    assert oldest.content.startswith("summary "), (
        f"oldest message must use short_content, got: {oldest.content[:60]!r}"
    )
    # Last 20 must be full.
    for recent in req.history[-20:]:
        assert recent.content.startswith("long content "), (
            f"recent message must be full, got: {recent.content[:60]!r}"
        )
