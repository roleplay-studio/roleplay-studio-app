"""Tests for BotImportService — V1/V2/V3 character card import (Task 2)."""

from __future__ import annotations

import base64
import json
import zlib
from io import BytesIO
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
from character_card import (
    CharacterCardData,
    CharacterCardParseError,
    parse_character_card,
)
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from app.application.dto import AddKnowledgeEntryCommand
from app.application.services.bot_import import BotImportService

# ── Test helpers (copied from test_character_card_parser pattern) ─────


def _build_v2_card_png(card_data: dict[str, Any], png_size: tuple[int, int] = (64, 64)) -> bytes:
    """Build a PNG with V2 character card embedded in 'chara' tEXt chunk."""
    payload = {
        "spec": "chara-card-v2",
        "spec_version": "2.0",
        "data": card_data,
    }
    img = Image.new("RGB", png_size, color=(100, 150, 200))
    meta = PngInfo()
    raw = json.dumps(payload).encode("utf-8")
    encoded = base64.b64encode(zlib.compress(raw)).decode("ascii")
    meta.add_text("chara", encoded)
    buf = BytesIO()
    img.save(buf, format="PNG", pnginfo=meta)
    return buf.getvalue()


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def fake_card() -> dict[str, Any]:
    return {
        "name": "Luna",
        "description": "A dream weaver",
        "personality": "Gentle",
        "scenario": "Garden",
        "first_mes": "Hello!",
        "alternate_greetings": ["Hi!", "Hey!"],
        "system_prompt": "Speak verse",
        "post_history_instructions": "End with ?",
        "creator_notes": "v1",
        "tags": ["Fantasy"],
        "character_book": {
            "entries": [
                {"content": "lore 1"},
                {"content": "lore 2"},
            ]
        },
    }


@pytest.fixture
def bot_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.create = AsyncMock(return_value=42)
    return repo


@pytest.fixture
def knowledge_svc() -> AsyncMock:
    svc = AsyncMock()
    svc.add_entry = AsyncMock()
    return svc


# ── Tests ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_import_from_card_creates_bot_with_mapped_fields(
    tmp_path, fake_card, bot_repo, knowledge_svc
) -> None:
    """V2 card → bot with all fields mapped per spec."""
    png = _build_v2_card_png(fake_card)
    svc = BotImportService(
        bot_repo=bot_repo,
        knowledge_service=knowledge_svc,
        avatar_dir=tmp_path,
    )

    bot_id = await svc.import_from_card(png, ".png")

    assert bot_id == 42
    bot_repo.create.assert_awaited_once()
    # The first three arguments are positional per the BotRepository protocol.
    args, kwargs = bot_repo.create.await_args
    name, personality, first_message = args[0], args[1], args[2]
    assert name == "Luna"
    # V2 personality + post_history_instructions go into Bot.personality.
    # V2 system_prompt is a scenario-level instruction and goes into
    # Bot.scenario alongside the V2 scenario field.
    assert "Gentle" in personality
    assert "End with ?" in personality
    assert "Speak verse" not in personality
    assert first_message == "Hello!"
    assert kwargs["alternate_greetings"] == ["Hi!", "Hey!"]
    assert kwargs["categories"] == ["Fantasy"]
    # Creator notes are kept SEPARATE from description per the V2
    # spec ("creator_notes MUST NOT be used inside prompts"). The
    # BotImportService reads card.creator_notes separately and only
    # routes it into Bot.description when no actual description was
    # provided. In this test, both are present, so the description
    # passes through clean and the creator_notes lives in
    # card.creator_notes (the test doesn't check that field — that's
    # the library's job; see character-card's test_spec_compliance).
    assert "v1" not in kwargs["description"]
    assert "A dream weaver" in kwargs["description"]
    # Scenario is composed of V2 scenario + V2 system_prompt.
    scenario = kwargs["scenario"]
    assert "Garden" in scenario
    assert "Speak verse" in scenario
    # And system_prompt does NOT also leak into personality.
    assert "Speak verse" not in personality


@pytest.mark.asyncio
async def test_import_from_card_imports_lorebook_as_knowledge(
    tmp_path, fake_card, bot_repo, knowledge_svc
) -> None:
    """Each character_book entry → AddKnowledgeEntryCommand."""
    png = _build_v2_card_png(fake_card)
    svc = BotImportService(
        bot_repo=bot_repo,
        knowledge_service=knowledge_svc,
        avatar_dir=tmp_path,
    )

    await svc.import_from_card(png, ".png")

    assert knowledge_svc.add_entry.await_count == 2
    calls = knowledge_svc.add_entry.await_args_list
    contents = [c.args[0].content for c in calls]
    assert "lore 1" in contents
    assert "lore 2" in contents
    for c in calls:
        assert isinstance(c.args[0], AddKnowledgeEntryCommand)
        assert c.args[0].bot_id == 42


@pytest.mark.asyncio
async def test_import_from_card_saves_avatar_to_avatar_dir(
    tmp_path, fake_card, bot_repo, knowledge_svc
) -> None:
    """Avatar bytes are written into the avatar_dir under a unique stem."""
    png = _build_v2_card_png(fake_card)
    svc = BotImportService(
        bot_repo=bot_repo,
        knowledge_service=knowledge_svc,
        avatar_dir=tmp_path,
    )

    await svc.import_from_card(png, ".png")

    files = list(tmp_path.iterdir())
    assert len(files) >= 1
    # File should be a PNG (extension .png).
    assert any(f.suffix.lower() in {".png", ".jpg", ".webp"} for f in files)


@pytest.mark.asyncio
async def test_import_from_card_invalid_png_raises(bot_repo, knowledge_svc) -> None:
    """Not a PNG → CharacterCardParseError propagates."""
    svc = BotImportService(
        bot_repo=bot_repo,
        knowledge_service=knowledge_svc,
        avatar_dir="/tmp",
    )

    with pytest.raises(CharacterCardParseError):
        await svc.import_from_card(b"not a png", ".png")


@pytest.mark.asyncio
async def test_import_dungeon_core_simulator_real_png(tmp_path, bot_repo, knowledge_svc) -> None:
    """Regression: import a real V2 card from disk and verify the
    V2-to-Bot field mapping matches the new semantics.

    The Dungeon Core Simulator card has a non-trivial mix of fields:
    - personality: '' (empty)
    - scenario: '' (empty)
    - system_prompt: ~587 chars of LLM instructions
    - post_history_instructions: ~5203 chars of output format
    - first_mes: ~1081 chars of roleplay opening
    - alternate_greetings: 2 long HTML-comment-prefixed greetings

    Under the new mapping the system_prompt must end up in
    Bot.scenario (not Bot.personality) and the post_history_instructions
    in Bot.personality — so the LLM system message gets the scenario-
    level instructions, and the per-turn output rules stay attached
    to the character description.
    """
    png_path = (
        Path(__file__).resolve().parent.parent / "main_dungeon-core-simulator-d8ba890f_spec_v2.png"
    )
    if not png_path.exists():
        pytest.skip(f"Fixture PNG not found at {png_path}")

    png_bytes = png_path.read_bytes()
    svc = BotImportService(
        bot_repo=bot_repo,
        knowledge_service=knowledge_svc,
        avatar_dir=tmp_path,
    )

    bot_id = await svc.import_from_card(png_bytes, ".png")
    assert bot_id == 42

    args, kwargs = bot_repo.create.await_args
    name, personality, first_message = args[0], args[1], args[2]
    assert name == "Dungeon Core Simulator"
    assert first_message.startswith("<!--Various scholars")
    assert kwargs["alternate_greetings"]  # 2 long greetings present

    # The distinctive phrases from each V2 field. We assert presence
    # in the right Bot field rather than the wrong one.
    scenario = kwargs["scenario"]
    # system_prompt phrase (LLM instructions) — must be in scenario.
    assert "Always write in the second person" in scenario, (
        "V2 system_prompt was not folded into Bot.scenario — the LLM "
        "system-level instructions would be lost from the prompt."
    )
    # scenario field itself is empty in this card, so scenario should
    # essentially be just the system_prompt (no V2 scenario text to join).
    # We do NOT assert "scenario" content because the card's V2 scenario
    # is empty.

    # post_history_instructions phrase (per-turn output rules) — must
    # be in personality, not scenario.
    assert "Always assume that HTML comments are unknown" in personality, (
        "V2 post_history_instructions was not folded into Bot.personality."
    )
    assert "Always assume that HTML comments are unknown" not in scenario, (
        "post_history_instructions leaked into Bot.scenario — it should "
        "stay with the character description in Bot.personality."
    )

    # The base personality is empty in this card, so personality should
    # be only the post_history_instructions (possibly with separator).
    assert "Always assume that HTML comments are unknown" in personality


@pytest.mark.asyncio
async def test_import_from_card_no_lorebook_works(tmp_path, bot_repo, knowledge_svc) -> None:
    """Card with no character_book → bot is created, no knowledge calls."""
    card = {
        "name": "Simple",
        "description": "Plain",
        "personality": "Calm",
        "first_mes": "Hi",
    }
    png = _build_v2_card_png(card)
    svc = BotImportService(
        bot_repo=bot_repo,
        knowledge_service=knowledge_svc,
        avatar_dir=tmp_path,
    )

    bot_id = await svc.import_from_card(png, ".png")

    assert bot_id == 42
    knowledge_svc.add_entry.assert_not_awaited()


@pytest.mark.asyncio
async def test_import_from_card_filters_empty_lorebook_entries(
    tmp_path, bot_repo, knowledge_svc
) -> None:
    """Empty character_book entries are filtered out before import."""
    card = {
        "name": "Filtered",
        "description": "",
        "personality": "Mysterious",
        "first_mes": "Greetings",
        "character_book": {
            "entries": [
                {"content": "real lore"},
                {"content": ""},
                {"content": "   "},
            ]
        },
    }
    png = _build_v2_card_png(card)
    svc = BotImportService(
        bot_repo=bot_repo,
        knowledge_service=knowledge_svc,
        avatar_dir=tmp_path,
    )

    await svc.import_from_card(png, ".png")

    assert knowledge_svc.add_entry.await_count == 1


# Sanity-check that our helper builds a PNG that the parser can read back.
def test_helper_png_round_trips_with_parser(fake_card) -> None:
    """Self-check: the helper produces a card parse_character_card understands."""
    png = _build_v2_card_png(fake_card)
    parsed = parse_character_card(png, ".png")
    assert isinstance(parsed, CharacterCardData)
    assert parsed.name == "Luna"


# ── V2 fallback chain ──────────────────────────────────────────────────
# Regression tests for review2: V2 authors (e.g. character_card_creator,
# luna_the_dream_weaver, hogwarts-simulator) leave the dedicated
# ``personality`` field empty and push the whole character sheet into
# ``description``. Before the fix, ``Bot.personality`` came out as
# ``""`` and the LLM saw a bot with no character at runtime. The fix
# chains ``personality → system_prompt → description`` so the LLM
# always gets a non-empty personality, and drops the duplicated long
# sheet from ``Bot.description`` when it was consumed for the fallback.


@pytest.mark.asyncio
async def test_import_falls_back_to_description_when_personality_empty(
    tmp_path, bot_repo, knowledge_svc
) -> None:
    """Card with empty V2 personality + long description: bot gets the
    description text as personality, not an empty string.
    """
    card = {
        "name": "Luna",
        "description": ("## {{char}}'s Identity\nName: Luna\nOccupation: Dream Weaver\n") * 5,
        "personality": "",
        "system_prompt": "",
        "scenario": "",
        "first_mes": "*She appears at the edge of sleep.*",
        "creator_notes": "Sleep well!",
        "tags": ["Fantasy"],
    }
    png = _build_v2_card_png(card)
    svc = BotImportService(bot_repo=bot_repo, knowledge_service=knowledge_svc, avatar_dir=tmp_path)

    await svc.import_from_card(png, ".png")

    args, kwargs = bot_repo.create.await_args
    personality = args[1]
    assert "Identity" in personality
    assert "Dream Weaver" in personality
    # Description was consumed for the personality fallback, so the
    # description field should NOT also hold the long character sheet.
    # We surface only the (short) creator notes instead.
    assert "Identity" not in kwargs["description"]
    assert kwargs["description"] == "Sleep well!"


@pytest.mark.asyncio
async def test_import_falls_back_to_system_prompt_when_no_personality(
    tmp_path, bot_repo, knowledge_svc
) -> None:
    """Card with empty personality + non-empty system_prompt: bot gets
    system_prompt as personality signal (and the description stays put
    because both fields are distinct).
    """
    card = {
        "name": "Dungeon",
        "description": "As a dungeon core, {{user}} can expand their dungeon.",
        "personality": "",
        "system_prompt": "{{char}} is not a character, but a scenario.",
        "scenario": "Underground.",
        "first_mes": "<!--Mana: 100-->",
        "creator_notes": "Be the dungeon core of your dreams!",
        "tags": ["RPG"],
    }
    png = _build_v2_card_png(card)
    svc = BotImportService(bot_repo=bot_repo, knowledge_service=knowledge_svc, avatar_dir=tmp_path)

    await svc.import_from_card(png, ".png")

    args, kwargs = bot_repo.create.await_args
    personality = args[1]
    assert "not a character" in personality
    # Both system_prompt and description are present and distinct —
    # both belong in the personality block, and the description field
    # keeps the original description (no dedup needed).
    assert "dungeon core" in personality
    assert "expand their dungeon" in kwargs["description"]


@pytest.mark.asyncio
async def test_import_keeps_description_when_personality_is_present(
    tmp_path, bot_repo, knowledge_svc
) -> None:
    """Standard V2 card (Bratty Step-Sisters style): V2 personality is
    non-empty, V2 description stays in ``Bot.description`` as before.
    """
    card = {
        "name": "Bratty Step-Sisters",
        "description": "{{char}} is two separate characters: Mira and Faye.",
        "personality": "<p>Your Bratty Step-Sisters are FIGHTING over you again.</p>",
        "scenario": "A year ago your parent married a wealthy woman.",
        "first_mes": "*The front door clicks shut*",
        "creator_notes": "",
        "tags": ["Drama"],
    }
    png = _build_v2_card_png(card)
    svc = BotImportService(bot_repo=bot_repo, knowledge_service=knowledge_svc, avatar_dir=tmp_path)

    await svc.import_from_card(png, ".png")

    args, kwargs = bot_repo.create.await_args
    personality = args[1]
    # personality came from V2 personality — description untouched.
    assert "FIGHTING" in personality
    assert "Mira and Faye" in kwargs["description"]


@pytest.mark.asyncio
async def test_import_empty_description_when_no_fallback_sources(
    tmp_path, bot_repo, knowledge_svc
) -> None:
    """A V2 card with everything blank (only name + first_mes) should
    still import without errors. Description ends up empty.
    """
    card = {
        "name": "Empty",
        "description": "",
        "personality": "",
        "system_prompt": "",
        "post_history_instructions": "",
        "scenario": "",
        "first_mes": "Hi.",
        "tags": [],
    }
    png = _build_v2_card_png(card)
    svc = BotImportService(bot_repo=bot_repo, knowledge_service=knowledge_svc, avatar_dir=tmp_path)

    await svc.import_from_card(png, ".png")

    args, kwargs = bot_repo.create.await_args
    assert args[1] == ""  # Bot.personality
    assert kwargs["description"] == ""  # Bot.description
