"""Starter bot loaders.

Supports two on-disk formats, selected by file extension:

* ``.json`` — plain JSON with fields: name, personality, first_message, scenario, categories
* ``.png``  — PNG image whose metadata holds the same fields. We accept
              two layouts:

  1. **Flat tEXt** — one ``tEXt`` chunk per field (``name``,
     ``personality``, …). This is what our own helper
     ``scripts/make_puro_png.py`` writes.
  2. **SillyTavern V2** — a single ``chara`` (or ``ccv3``) tEXt chunk
     whose value is ``base64(json)`` (with or without zlib). Decoded
     via :mod:`character_card`, the same parser
     used by :class:`BotImportService`. We map the parsed
     :class:`CharacterCardData` back to the flat shape the rest of
     the starter-bot pipeline expects.

The V2 layout wins when the flat layout is incomplete (missing any
required field) — that way a card whose V2 author left the
``personality`` field empty still loads cleanly via the fallback
chain (``personality → system_prompt → description``).
"""

from __future__ import annotations

import json
import zlib
from pathlib import Path
from typing import Any

from character_card import (
    CharacterCardData,
    CharacterCardParseError,
    parse_character_card,
)

REQUIRED_FIELDS = ("name", "personality", "first_message", "scenario")
PNG_TEXT_KEYS = {
    "name": "name",
    "personality": "personality",
    "first_message": "first_message",
    "scenario": "scenario",
    "categories": "categories",
}

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_TERMINATOR = b"IEND"


def _validate(data: dict[str, Any], source: str) -> dict[str, Any]:
    """Validate required fields and normalise ``categories`` to a list of str."""
    missing = [k for k in REQUIRED_FIELDS if not data.get(k)]
    if missing:
        raise ValueError(f"{source} missing required fields: {', '.join(missing)}")

    categories = data.get("categories", [])
    if isinstance(categories, str):
        # Allow comma-separated: "Anime, Romance" → ["Anime", "Romance"]
        categories = [c.strip() for c in categories.split(",") if c.strip()]
    elif not isinstance(categories, list):
        categories = list(categories)

    return {
        "name": str(data["name"]).strip(),
        "personality": str(data["personality"]).strip(),
        "first_message": str(data["first_message"]).strip(),
        "scenario": str(data["scenario"]).strip(),
        "categories": [str(c).strip() for c in categories if str(c).strip()],
    }


def load_from_json(path: Path) -> dict[str, Any]:
    """Load and validate a starter bot from a JSON file."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object at the top level")
    return _validate(raw, str(path))


def _read_png_text_chunks(path: Path) -> dict[str, str]:
    """Parse PNG text chunks (``tEXt``, ``iTXt``, ``zTXt``) without Pillow.

    Returns a ``{keyword: text}`` mapping. ``zTXt`` chunks are decompressed.
    Unknown chunk types are skipped. Raises ``ValueError`` if the file is
    not a valid PNG.

    This is the flat-layout reader. It deliberately accepts **any**
    tEXt chunk key — the caller's job is to look up the bot fields
    (``name``, ``personality``, …). That keeps it independent from
    the V2 character-card spec, which lives in
    :mod:`character_card`.
    """
    with open(path, "rb") as f:
        data = f.read()

    if not data.startswith(_PNG_SIGNATURE):
        raise ValueError(f"{path} is not a PNG file (bad signature)")

    result: dict[str, str] = {}
    pos = len(_PNG_SIGNATURE)

    while pos < len(data):
        # Each chunk: length(4) + type(4) + data(length) + crc(4)
        if pos + 8 > len(data):
            break
        length = int.from_bytes(data[pos : pos + 4], "big")
        chunk_type = data[pos + 4 : pos + 8]
        chunk_end = pos + 8 + length + 4
        if chunk_end > len(data):
            break
        chunk_data = data[pos + 8 : pos + 8 + length]

        if chunk_type == _TERMINATOR:
            break

        try:
            chunk_type_str = chunk_type.decode("ascii")
        except UnicodeDecodeError:
            chunk_type_str = ""

        if chunk_type_str == "tEXt":
            # null-separated: keyword\0text
            sep = chunk_data.find(b"\0")
            if sep != -1:
                keyword = chunk_data[:sep].decode("latin-1", errors="replace")
                text = chunk_data[sep + 1 :].decode("utf-8", errors="replace")
                result[keyword] = text
        elif chunk_type_str == "iTXt":
            # keyword\0comp_flag(1)comp_method(1)lang\0trans_keyword\0text
            sep1 = chunk_data.find(b"\0")
            if sep1 != -1:
                keyword = chunk_data[:sep1].decode("latin-1", errors="replace")
                rest = chunk_data[sep1 + 1 :]
                if len(rest) >= 2:
                    comp_flag = rest[1]
                    sep2 = rest.find(b"\0", 2)
                    if sep2 != -1:
                        sep3 = rest.find(b"\0", sep2 + 1)
                        if sep3 != -1:
                            text_bytes = rest[sep3 + 1 :]
                            if comp_flag:
                                text_bytes = zlib.decompress(text_bytes)
                            result[keyword] = text_bytes.decode("utf-8", errors="replace")
        elif chunk_type_str == "zTXt":
            # keyword\0comp_method(1)compressed_text
            sep = chunk_data.find(b"\0")
            if sep != -1 and len(chunk_data) > sep + 1:
                keyword = chunk_data[:sep].decode("latin-1", errors="replace")
                compressed = chunk_data[sep + 2 :]
                try:
                    decompressed = zlib.decompress(compressed)
                    result[keyword] = decompressed.decode("utf-8", errors="replace")
                except zlib.error:
                    pass

        pos = chunk_end

    return result


def _card_to_flat(card: CharacterCardData) -> dict[str, Any]:
    """Map a :class:`CharacterCardData` to the flat starter-bot shape.

    The V2 spec splits the system-level guidance into several places
    (``personality``, ``system_prompt``, ``description``); the
    starter-bot pipeline only has two text columns, so we apply the
    same fallback chain the import service uses — ``personality →
    system_prompt → description``. ``scenario`` is a separate
    field on the Bot, so we don't fold it into personality.
    """
    # Personality fallback chain. Some V2 cards (e.g. luna_the_dream_weaver,
    # character_card_creator) leave ``personality`` empty and put the
    # whole sheet under ``description``. Without a fallback the LLM
    # would see a bot with no character at all.
    personality = card.personality.strip() or card.system_prompt.strip() or card.description.strip()

    # Scenario fallback. Same cards often push the world/framing into
    # ``description`` rather than the dedicated ``scenario`` field.
    scenario = card.scenario.strip() or card.description.strip()

    # first_mes fallback to first alternate_greeting when empty.
    first_message = card.first_message.strip()
    if not first_message and card.alternate_greetings:
        first_message = (card.alternate_greetings[0] or "").strip()

    return {
        "name": card.name.strip(),
        "personality": personality,
        "first_message": first_message,
        "scenario": scenario,
        "categories": [str(c).strip() for c in card.tags if str(c).strip()],
    }


def _try_v2_card(path: Path, file_bytes: bytes) -> dict[str, Any] | None:
    """Try the V2 layout via :func:`parse_character_card`.

    Returns the flat-mapped bot on success, or ``None`` if the bytes
    don't carry a recognisable V2/V1 payload. Field-validation
    failures (missing ``name``, no greeting) raise — those are
    never "not a V2 card" cases.
    """
    try:
        card = parse_character_card(file_bytes, ".png")
    except CharacterCardParseError:
        return None
    return _card_to_flat(card)


def load_from_png(path: Path) -> dict[str, Any]:
    """Load and validate a starter bot from PNG metadata.

    Tries the V2 layout (single ``chara``/``ccv3`` chunk via
    :func:`parse_character_card`) first, falls back to the flat
    tEXt layout when V2 is absent. The flat layout wins when it
    is complete; V2 only fills in missing fields.
    """
    file_bytes = path.read_bytes()
    flat: dict[str, Any] = {}

    # Flat tEXt layout — always try it. Independent of the V2 parser,
    # so cards with hand-rolled tEXt chunks (puro.png, our wizard
    # fixtures) load cleanly without depending on PIL or any V2 logic.
    # A bad PNG signature is a hard error: we don't want the
    # downstream "missing required fields" message to mask a wrong
    # file extension.
    chunks = _read_png_text_chunks(path)

    for field, png_key in PNG_TEXT_KEYS.items():
        if png_key in chunks:
            flat[field] = chunks[png_key]

    if all(flat.get(k) for k in REQUIRED_FIELDS):
        return _validate(flat, str(path))

    # Flat layout is incomplete — try V2.
    v2 = _try_v2_card(path, file_bytes)
    if v2 is not None:
        merged = {**flat, **v2}
        if all(merged.get(k) for k in REQUIRED_FIELDS):
            return _validate(merged, str(path))

    # Neither layout produced a valid card — fall through to the
    # original error path so the caller sees the missing-field list.
    return _validate(flat, str(path))


def load_starter_bot(path: Path) -> dict[str, Any]:
    """Dispatch by suffix. ``.png`` → PNG loader, anything else → JSON loader."""
    if path.suffix.lower() == ".png":
        return load_from_png(path)
    return load_from_json(path)
