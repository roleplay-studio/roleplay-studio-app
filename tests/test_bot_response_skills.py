"""Tests for BotResponse.skills projection. See spec §6.6.

The API serves the bot's attached skills as ``skills: list[BotSkillDTO]``
(slim, no instruction) and ``skills_invalid: list[int]`` for any
IDs that no longer resolve to a live GlobalSkill. Mirrors the
existing ``categories`` / ``categories_invalid`` pattern.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from app.application.dto import BotResponse


def _make_bot(skill_ids_json: str = "[]") -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        name="Lili",
        personality="",
        scenario="",
        first_message="",
        description="",
        avatar_path=None,
        categories="[]",
        alternate_greetings="[]",
        bot_type="rp",
        mes_example="",
        dynamic_system_prompt="",
        world_state_prompt="",
        skill_ids=skill_ids_json,
    )


def test_from_orm_bot_with_no_skills_returns_empty_lists():
    bot = _make_bot(skill_ids_json="[]")
    resp = BotResponse.from_orm_bot(bot)
    assert resp.skills == []
    assert resp.skills_invalid == []


def test_from_orm_bot_parses_skill_ids_json():
    bot = _make_bot(skill_ids_json=json.dumps([3, 7, 11]))
    resp = BotResponse.from_orm_bot(bot)
    # No valid_skill_ids provided → list goes straight to skills,
    # invalid is empty (no cross-reference possible).
    assert resp.skills == [3, 7, 11]
    assert resp.skills_invalid == []


def test_from_orm_bot_corrupted_skill_ids_falls_back_to_empty():
    bot = _make_bot(skill_ids_json="not-json{[")
    resp = BotResponse.from_orm_bot(bot)
    # Defensive — never crash the API.
    assert resp.skills == []
    assert resp.skills_invalid == []


def test_from_orm_bot_cross_references_valid_skill_ids():
    """With valid_skill_ids supplied, the orphan IDs land in skills_invalid."""
    bot = _make_bot(skill_ids_json=json.dumps([3, 7, 11, 99]))
    resp = BotResponse.from_orm_bot(bot, valid_skill_ids={3, 7, 11})
    assert resp.skills == [3, 7, 11, 99]
    assert resp.skills_invalid == [99]


def test_from_orm_bot_handles_missing_skill_ids_attribute():
    """Old bot rows predating the column (None / missing attr) → empty."""
    bot = SimpleNamespace(
        id=1,
        name="x",
        personality="",
        scenario="",
        first_message="",
        description="",
        avatar_path=None,
        categories="[]",
        alternate_greetings="[]",
        bot_type="rp",
        mes_example="",
        dynamic_system_prompt="",
        world_state_prompt="",
        # NO skill_ids attribute
    )
    resp = BotResponse.from_orm_bot(bot)
    assert resp.skills == []
    assert resp.skills_invalid == []


def test_bot_response_skill_field_default_empty():
    """BotResponse without explicit skills (e.g. older callers) defaults to []."""
    resp = BotResponse(id=1, name="x")
    assert resp.skills == []
    assert resp.skills_invalid == []
