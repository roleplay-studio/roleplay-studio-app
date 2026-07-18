"""Tests for SkillDTOs + ConflictError. See spec §5.1, §5.2, §6.4."""
import pytest
from pydantic import ValidationError

from app.application.dto import (
    BotSkillDTO,
    ConflictErrorResponse,
    CreateSkillCommand,
    SkillDTO,
    UpdateBotSkillsCommand,
    UpdateSkillCommand,
)
from app.application.exceptions import ConflictError

# ── CreateSkillCommand ────────────────────────────────────────────


def test_create_skill_command_strips_and_validates_name():
    cmd = CreateSkillCommand(
        name="  Sarcastic  ", description="x", instruction="y", tags=["a"]
    )
    assert cmd.name == "Sarcastic"


def test_create_skill_command_rejects_empty_name():
    with pytest.raises(ValidationError):
        CreateSkillCommand(name="   ", description="x", instruction="y", tags=[])


def test_create_skill_command_rejects_oversized_name():
    with pytest.raises(ValidationError):
        CreateSkillCommand(
            name="x" * 65, description="x", instruction="y", tags=[]
        )


def test_create_skill_command_rejects_empty_instruction():
    with pytest.raises(ValidationError):
        CreateSkillCommand(name="X", description="", instruction="", tags=[])


def test_create_skill_command_rejects_oversized_instruction():
    with pytest.raises(ValidationError):
        CreateSkillCommand(
            name="X", description="", instruction="x" * 4001, tags=[]
        )


def test_create_skill_command_rejects_oversized_description():
    with pytest.raises(ValidationError):
        CreateSkillCommand(
            name="X", description="x" * 301, instruction="y", tags=[]
        )


def test_create_skill_command_normalizes_tags_lower_and_dedup():
    cmd = CreateSkillCommand(
        name="X",
        description="",
        instruction="y",
        tags=["Tone", "DIALOG", "tone"],  # mixed case + duplicate
    )
    assert cmd.tags == ["tone", "dialog"]


def test_create_skill_command_strips_whitespace_from_tags():
    cmd = CreateSkillCommand(
        name="X",
        description="",
        instruction="y",
        tags=["  Tone  ", "dialog"],
    )
    assert cmd.tags == ["tone", "dialog"]


def test_create_skill_command_drops_empty_tags():
    cmd = CreateSkillCommand(
        name="X",
        description="",
        instruction="y",
        tags=["Tone", "", "  ", "dialog"],
    )
    assert cmd.tags == ["tone", "dialog"]


def test_create_skill_command_defaults_tags_to_empty_list():
    cmd = CreateSkillCommand(name="X", description="", instruction="y")
    assert cmd.tags == []


# ── UpdateSkillCommand ────────────────────────────────────────────


def test_update_skill_command_all_optional():
    cmd = UpdateSkillCommand()
    assert cmd.name is None
    assert cmd.description is None
    assert cmd.instruction is None
    assert cmd.tags is None


def test_update_skill_command_partial_only_supplied_fields():
    cmd = UpdateSkillCommand(description="new")
    assert cmd.description == "new"
    assert cmd.name is None
    assert cmd.tags is None


def test_update_skill_command_normalizes_tags_when_supplied():
    cmd = UpdateSkillCommand(tags=["A", "b", "a"])
    assert cmd.tags == ["a", "b"]


# ── UpdateBotSkillsCommand ───────────────────────────────────────


def test_update_bot_skills_command_defaults_to_empty_list():
    cmd = UpdateBotSkillsCommand()
    assert cmd.skill_ids == []


def test_update_bot_skills_command_accepts_explicit_list():
    cmd = UpdateBotSkillsCommand(skill_ids=[1, 2, 3])
    assert cmd.skill_ids == [1, 2, 3]


# ── SkillDTO / BotSkillDTO ────────────────────────────────────────


def test_skill_dto_round_trip():
    """SkillDTO is a response shape — verify all fields are serialisable."""
    dto = SkillDTO(
        id=1,
        name="Sarcastic",
        description="d",
        instruction="i",
        tags=["tone"],
        created_at="2026-07-17T00:00:00",  # ISO string parses via datetime
        updated_at="2026-07-17T00:00:00",
    )
    payload = dto.model_dump()
    assert payload["id"] == 1
    assert payload["name"] == "Sarcastic"
    assert payload["tags"] == ["tone"]


def test_bot_skill_dto_carries_no_instruction():
    """BotSkillDTO is the lightweight projection for list_bots.

    Saves bandwidth — full instruction only via GET /api/skills/{id}.
    See spec §5.3.
    """
    dto = BotSkillDTO(id=1, name="Sarcastic", description="d")
    payload = dto.model_dump()
    assert set(payload.keys()) == {"id", "name", "description"}
    assert "instruction" not in payload


# ── ConflictError ─────────────────────────────────────────────────


def test_conflict_error_carries_attached_to():
    err = ConflictError("Skill is in use", attached_to=[1, 2, 3])
    assert str(err) == "Skill is in use"
    assert err.attached_to == [1, 2, 3]
    # http_status carries the 409 mapping (parity with ValidationError).
    assert err.http_status == 409


def test_conflict_error_defaults_attached_to_empty_list():
    err = ConflictError("Not found")
    assert err.attached_to == []


def test_conflict_error_response_dto():
    """ConflictErrorResponse is the wire shape returned by the 409 handler."""
    resp = ConflictErrorResponse(detail="in use", attached_to=[1, 2])
    assert resp.detail == "in use"
    assert resp.attached_to == [1, 2]


# ── Cross-spec consistency check ──────────────────────────────────


def test_skill_dto_tags_default_empty():
    """Empty tags list default — matches SqlAlchemySkillRepository contract."""
    dto = SkillDTO(
        id=1,
        name="X",
        description="d",
        instruction="i",
        created_at="2026-07-17T00:00:00",
        updated_at="2026-07-17T00:00:00",
    )
    assert dto.tags == []  # default_factory=list
