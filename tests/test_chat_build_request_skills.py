"""Tests for ChatService._build_request populating ConversationRequest.skills.

Phase 4 / Task 11. Verifies that ``_build_request``:
1. Reads ``Bot.skill_ids`` (JSON list)
2. Calls ``SkillService.list_for_bot_with_ids`` to resolve SkillDTOs
3. Passes them into ``ConversationRequest.skills``

Also covers the graceful degradation path (no skill service wired
→ empty list, never crash). See spec §7.3 + AGENTS.md §1.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from app.application.dto import (
    SendMessageCommand,
    SkillDTO,
)
from app.application.services.chat import ChatService

# ── Fakes ────────────────────────────────────────────────────────


class _FakeBots:
    """Just enough of BotRepository to satisfy ``_build_request``."""

    def __init__(self, bot) -> None:
        self._bot = bot

    async def get(self, bot_id: int):
        return self._bot


class _FakeMessages:
    async def list_for_thread(self, thread_id, limit, before_id=None):
        return []

    async def list_active_branch(self, thread_id):
        return []

    async def get_previous_assistant_state(self, thread_id, before_message_id=None):
        return ""

    async def list_state_for_thread(self, thread_id):
        return []


class _FakeKnowledge:
    async def has_documents(self, bot_id):
        return False

    async def search(self, bot_id, query, top_k):
        return []


class _FakeOrchestrator:
    pass


class _FakeSkillService:
    """Records the skill_ids it was asked to resolve."""

    def __init__(self, skills_by_id: dict[int, SkillDTO]) -> None:
        self._skills = skills_by_id
        self.last_requested_ids: list[int] | None = None

    async def list_for_bot_with_ids(self, skill_ids: list[int]):
        self.last_requested_ids = list(skill_ids)
        return [self._skills[i] for i in skill_ids if i in self._skills]


def _make_skill(skill_id: int, name: str) -> SkillDTO:
    from datetime import datetime

    return SkillDTO(
        id=skill_id,
        name=name,
        description="d",
        instruction="i",
        tags=[],
        created_at=datetime(2026, 7, 17),
        updated_at=datetime(2026, 7, 17),
    )


def _make_bot(skill_ids: list[int] | None = None):
    """Construct a SimpleNamespace stand-in for the Bot SQLModel row.

    ChatService accesses attrs only (no methods), so a SimpleNamespace
    is enough. ``skill_ids`` defaults to ``"[]"`` matching the SQLModel
    default.
    """
    return SimpleNamespace(
        id=1,
        name="Lili",
        personality="friendly",
        scenario="",
        first_message="",
        bot_type="rp",
        mes_example="",
        dynamic_system_prompt="",
        world_state_prompt="",
        skill_ids=json.dumps(skill_ids or []),
    )


def _build_service(skill_service=None) -> ChatService:
    """Build a ChatService with skill_service wired (or None)."""
    return ChatService(
        bots=_FakeBots(_make_bot()),  # type: ignore[arg-type]
        messages=_FakeMessages(),  # type: ignore[arg-type]
        knowledge=_FakeKnowledge(),  # type: ignore[arg-type]
        orchestrator=_FakeOrchestrator(),  # type: ignore[arg-type]
        skill_service=skill_service,
    )


# ── Tests ────────────────────────────────────────────────────────


async def test_build_request_resolves_skills_when_attached():
    """Bot has 2 skills → request.skills carries both SkillDTOs."""
    s1 = _make_skill(1, "Sarcastic")
    s2 = _make_skill(2, "Concise")
    fake_skills = _FakeSkillService({1: s1, 2: s2})
    svc = _build_service(skill_service=fake_skills)  # type: ignore[arg-type]

    # Patch the bot to have 2 attached skills.
    svc._bots = _FakeBots(_make_bot(skill_ids=[1, 2]))  # type: ignore[assignment]

    cmd = SendMessageCommand(thread_id=1, bot_id=1, user_input="hi")
    request = await svc._build_request(cmd)

    assert request.skills == [s1, s2]
    assert fake_skills.last_requested_ids == [1, 2]


async def test_build_request_skips_skill_resolution_when_bot_has_no_skills():
    """Empty Bot.skill_ids → skill_service is NOT consulted, request.skills = []."""
    fake_skills = _FakeSkillService({})
    svc = _build_service(skill_service=fake_skills)  # type: ignore[arg-type]
    # bot has empty skill_ids by default

    cmd = SendMessageCommand(thread_id=1, bot_id=1, user_input="hi")
    request = await svc._build_request(cmd)

    assert request.skills == []
    assert fake_skills.last_requested_ids is None  # never called


async def test_build_request_handles_corrupted_skill_ids_silently():
    """A bot row with corrupted ``skill_ids`` (not a valid JSON list)
    must not crash — fall back to empty list and log a warning.

    Defensive: this can happen if someone hand-edits the DB or runs
    an old migration that left nulls behind. The orchestrator will
    simply omit the <Skills> block.
    """
    svc = _build_service()
    svc._bots = _FakeBots(  # type: ignore[assignment]
        SimpleNamespace(
            id=1,
            name="X",
            personality="",
            scenario="",
            first_message="",
            bot_type="rp",
            mes_example="",
            dynamic_system_prompt="",
            world_state_prompt="",
            skill_ids="not-json{[",  # garbage
        )
    )

    cmd = SendMessageCommand(thread_id=1, bot_id=1, user_input="hi")
    request = await svc._build_request(cmd)

    assert request.skills == []


async def test_build_request_silently_drops_unknown_skill_ids():
    """If Bot.skill_ids has an orphan ID (skill was deleted), the
    service skips it. We pass the full list through and let
    ``SkillService.list_for_bot_with_ids`` drop missing ones.
    """
    s1 = _make_skill(1, "Sarcastic")
    # Bot references skill 1 + 999 (deleted). Only 1 should resolve.
    fake_skills = _FakeSkillService({1: s1})
    svc = _build_service(skill_service=fake_skills)  # type: ignore[arg-type]
    svc._bots = _FakeBots(_make_bot(skill_ids=[1, 999]))  # type: ignore[assignment]

    cmd = SendMessageCommand(thread_id=1, bot_id=1, user_input="hi")
    request = await svc._build_request(cmd)

    # Service was asked for both, returned only the one that exists.
    assert fake_skills.last_requested_ids == [1, 999]
    assert request.skills == [s1]


async def test_build_request_works_without_skill_service():
    """When skill_service is None (older bootstrap path), the
    request still builds — skills is empty list, never AttributeError.
    """
    svc = _build_service(skill_service=None)
    # Bot has 2 skills attached.
    svc._bots = _FakeBots(_make_bot(skill_ids=[1, 2]))  # type: ignore[assignment]

    cmd = SendMessageCommand(thread_id=1, bot_id=1, user_input="hi")
    request = await svc._build_request(cmd)

    # Graceful degradation — no service = no skills, never crash.
    assert request.skills == []
