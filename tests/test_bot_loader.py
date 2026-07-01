"""Tests for api.bot_loader — JSON and PNG (tEXt/iTXt/zTXt) starter bot loaders."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest
from PIL import Image
from PIL.PngImagePlugin import PngInfo

from api.bot_loader import (
    REQUIRED_FIELDS,
    _read_png_text_chunks,
    load_from_json,
    load_from_png,
    load_starter_bot,
)

VALID_CARD = {
    "name": "Puro",
    "personality": "Soft-spoken bookshop catgirl.",
    "first_message": "*looks up* Oh.",
    "scenario": "A quiet bookshop at night.",
    "categories": ["Slice of Life", "Literary"],
}


# ── Helpers ────────────────────────────────────────────────────────────


def _write_text_png(fields: dict[str, str], path: Path) -> None:
    """Write a real PNG with given key/text pairs as tEXt chunks (Pillow).

    tEXt chunks only hold strings, so callers should pass categories as a
    comma-separated string (matching the on-disk format we accept).
    """
    img = Image.new("RGB", (16, 16), color=(40, 40, 40))
    meta = PngInfo()
    for k, v in fields.items():
        meta.add_text(k, v)
    img.save(path, format="PNG", pnginfo=meta)


def _write_text_png_raw(fields: list[tuple[str, str]], path: Path) -> None:
    """Write a PNG with hand-built tEXt chunks (no Pillow metadata codepath).

    Mirrors the on-disk format produced by ``scripts/make_puro_png.py``.
    """
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)  # 1x1 RGB

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    idat = zlib.compress(b"\x00\xff\x00\x00")  # filter=None + 1 RGB pixel
    parts = [sig, chunk(b"IHDR", ihdr)]
    for k, v in fields:
        parts.append(chunk(b"tEXt", k.encode("latin-1") + b"\0" + v.encode("utf-8")))
    parts.append(chunk(b"IDAT", idat))
    parts.append(chunk(b"IEND", b""))
    path.write_bytes(b"".join(parts))


def _write_json(card: dict, path: Path) -> None:
    path.write_text(json.dumps(card), encoding="utf-8")


# ── JSON loader ────────────────────────────────────────────────────────


def test_load_from_json(tmp_path: Path):
    p = tmp_path / "puro.json"
    _write_json(VALID_CARD, p)

    loaded = load_from_json(p)
    assert loaded["name"] == "Puro"
    assert loaded["categories"] == ["Slice of Life", "Literary"]


def test_load_from_json_missing_field(tmp_path: Path):
    p = tmp_path / "bad.json"
    _write_json({"name": "Puro", "personality": "x"}, p)
    with pytest.raises(ValueError, match="missing required fields"):
        load_from_json(p)


def test_load_from_json_categories_comma_separated(tmp_path: Path):
    p = tmp_path / "puro.json"
    _write_json({**VALID_CARD, "categories": "Anime, Romance, Fluff"}, p)
    loaded = load_from_json(p)
    assert loaded["categories"] == ["Anime", "Romance", "Fluff"]


def test_load_from_json_not_object(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_from_json(p)


# ── PNG loader ─────────────────────────────────────────────────────────


def test_load_from_png_pillow(tmp_path: Path):
    p = tmp_path / "puro.png"
    # categories as comma-separated string (tEXt can't store lists)
    _write_text_png(
        {
            "name": "Puro",
            "personality": "Soft-spoken bookshop catgirl.",
            "first_message": "*looks up* Oh.",
            "scenario": "A quiet bookshop at night.",
            "categories": "Slice of Life, Literary",
        },
        p,
    )
    loaded = load_from_png(p)
    assert loaded["name"] == "Puro"
    assert loaded["personality"] == "Soft-spoken bookshop catgirl."
    assert loaded["categories"] == ["Slice of Life", "Literary"]


def test_load_from_png_handcrafted(tmp_path: Path):
    """Same content written without Pillow's pnginfo helper — covers raw chunk parsing."""
    p = tmp_path / "puro.png"
    _write_text_png_raw(
        [
            ("name", "Puro"),
            ("personality", "Soft-spoken."),
            ("first_message", "Hi."),
            ("scenario", "Bookshop."),
            ("categories", "Slice of Life, Literary"),
        ],
        p,
    )
    loaded = load_from_png(p)
    assert loaded["name"] == "Puro"
    assert loaded["categories"] == ["Slice of Life", "Literary"]


def test_load_from_png_missing_field(tmp_path: Path):
    p = tmp_path / "incomplete.png"
    _write_text_png({"name": "Puro", "personality": "x"}, p)  # missing first_message, scenario
    with pytest.raises(ValueError, match="missing required fields"):
        load_from_png(p)


def test_load_from_png_not_a_png(tmp_path: Path):
    p = tmp_path / "fake.png"
    p.write_bytes(b"not a png at all")
    with pytest.raises(ValueError, match="not a PNG"):
        load_from_png(p)


def test_read_png_text_chunks_ignores_unknown_keys(tmp_path: Path):
    p = tmp_path / "puro.png"
    _write_text_png(
        {
            "name": "Puro",
            "personality": "p",
            "first_message": "f",
            "scenario": "s",
            "author": "ignored",
            "software": "also ignored",
        },
        p,
    )
    chunks = _read_png_text_chunks(p)
    assert "author" in chunks
    assert "software" in chunks
    # And the loader doesn't crash on unknown keys:
    assert load_from_png(p)["name"] == "Puro"


# ── Dispatch ───────────────────────────────────────────────────────────


def test_load_starter_bot_dispatches_by_extension(tmp_path: Path):
    j = tmp_path / "puro.json"
    p = tmp_path / "puro.png"
    _write_json(VALID_CARD, j)
    # PNG fields use comma-separated categories (tEXt can't store lists)
    _write_text_png(
        {
            "name": "Puro",
            "personality": "Soft-spoken.",
            "first_message": "Hi.",
            "scenario": "Bookshop.",
            "categories": "Slice of Life, Literary",
        },
        p,
    )

    assert load_starter_bot(j)["name"] == "Puro"
    assert load_starter_bot(p)["name"] == "Puro"


def test_load_starter_bot_uppercase_png_extension(tmp_path: Path):
    p = tmp_path / "PURO.PNG"
    _write_text_png(
        {
            "name": "Puro",
            "personality": "p",
            "first_message": "f",
            "scenario": "s",
            "categories": "Slice of Life, Literary",
        },
        p,
    )
    assert load_starter_bot(p)["name"] == "Puro"


def test_load_starter_bot_real_artifact():
    """The committed bots_examples/puro.{json,png} must round-trip identically."""
    base = Path(__file__).resolve().parent.parent / "bots_examples"
    j = base / "puro.json"
    p = base / "puro.png"
    if not (j.exists() and p.exists()):
        pytest.skip("bots_examples/puro.{json,png} not present")
    assert load_from_json(j) == load_from_png(p)


# ── V2 character card (SillyTavern spec) ───────────────────────────────


def _write_v2_png(card_payload: dict, path: Path, *, zlib_compress: bool = True) -> None:
    """Write a PNG with a single ``chara`` tEXt chunk holding a V2 card.

    The V2 spec says the chunk is ``base64(zlib(json))``. Real-world
    tools (JanitorAI in particular) skip the zlib layer, so the
    ``zlib_compress`` parameter lets us write either layout.
    """
    import base64 as _b64

    raw = json.dumps(card_payload).encode("utf-8")
    if zlib_compress:
        raw = zlib.compress(raw)
    encoded = _b64.b64encode(raw).decode("ascii")

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    idat = zlib.compress(b"\x00\xff\x00\x00")
    path.write_bytes(
        b"".join(
            [
                sig,
                chunk(b"IHDR", ihdr),
                chunk(b"tEXt", b"chara\x00" + encoded.encode("ascii")),
                chunk(b"IDAT", idat),
                chunk(b"IEND", b""),
            ]
        )
    )


V2_FULL_CARD = {
    "spec": "chara-card-v2",
    "spec_version": "2.0",
    "data": {
        "name": "Luna, the Dream Weaver",
        "description": "A goddess who appears in dreams.",
        "personality": "Gentle, mysterious, watchful.",
        "scenario": "A shared dream at the edge of sleep.",
        "first_mes": "*She steps out of the mist, eyes like moonlight.*",
        "alternate_greetings": [],
        "tags": ["Fantasy", "Goddess", "Dreams"],
    },
}


def test_load_from_png_v2_full(tmp_path: Path):
    """V2 spec-conforming card: base64(zlib(json)) in a ``chara`` tEXt.

    Round-trips name, personality, scenario, first_message, categories.
    """
    p = tmp_path / "luna.png"
    _write_v2_png(V2_FULL_CARD, p, zlib_compress=True)

    loaded = load_from_png(p)
    assert loaded["name"] == "Luna, the Dream Weaver"
    assert loaded["personality"] == "Gentle, mysterious, watchful."
    assert loaded["scenario"] == "A shared dream at the edge of sleep."
    assert "moonlight" in loaded["first_message"]
    assert loaded["categories"] == ["Fantasy", "Goddess", "Dreams"]


def test_load_from_png_v2_no_zlib(tmp_path: Path):
    """Some authors (JanitorAI et al.) skip the zlib layer.

    The loader should still decode ``base64(json)`` and produce a
    valid bot.
    """
    p = tmp_path / "luna.png"
    _write_v2_png(V2_FULL_CARD, p, zlib_compress=False)

    loaded = load_from_png(p)
    assert loaded["name"] == "Luna, the Dream Weaver"
    assert loaded["categories"] == ["Fantasy", "Goddess", "Dreams"]


def test_load_from_png_v2_description_fallback(tmp_path: Path):
    """V2 cards that leave ``personality`` and ``scenario`` empty and
    push everything into ``description`` (e.g. character_card_creator,
    luna_the_dream_weaver) must still load. ``description`` becomes
    the personality source so the LLM gets the character sheet.
    """
    card = {
        "spec": "chara-card-v2",
        "spec_version": "2.0",
        "data": {
            "name": "Luna, the Dream Weaver",
            "description": "A goddess who appears in dreams.\n\n" * 5,
            "personality": "",
            "system_prompt": "",
            "scenario": "",
            "first_mes": "*A whisper from the dark.*",
            "tags": ["Fantasy"],
        },
    }
    p = tmp_path / "luna.png"
    _write_v2_png(card, p, zlib_compress=True)

    loaded = load_from_png(p)
    assert loaded["name"] == "Luna, the Dream Weaver"
    # description bled into personality so the LLM has something to
    # work with — not a blank string.
    assert "goddess" in loaded["personality"].lower()
    assert loaded["first_message"] == "*A whisper from the dark.*"


def test_load_from_png_v2_alternate_greetings_fallback(tmp_path: Path):
    """When ``first_mes`` is empty, use the first alternate_greeting."""
    card = {
        "spec": "chara-card-v2",
        "spec_version": "2.0",
        "data": {
            "name": "Echo",
            "description": "Quiet.",
            "personality": "Soft-spoken.",
            "scenario": "A library at midnight.",
            "first_mes": "",
            "alternate_greetings": ["*The candles flicker.*", "*She turns.*"],
            "tags": [],
        },
    }
    p = tmp_path / "echo.png"
    _write_v2_png(card, p, zlib_compress=True)

    loaded = load_from_png(p)
    assert loaded["first_message"] == "*The candles flicker.*"


def test_load_from_png_v2_corrupt_chara_raises(tmp_path: Path):
    """A ``chara`` chunk with no decodable payload still raises."""
    p = tmp_path / "bad.png"
    _write_v2_png({"this is not a chara card": True}, p, zlib_compress=True)
    # The V2 path returns missing-required-fields rather than a
    # raw decode error — that's the right contract for the caller.
    with pytest.raises(ValueError, match="missing required fields"):
        load_from_png(p)


# ── Real-artifact integration test (every file in bots_examples/) ──────


def test_every_starter_artifact_loads() -> None:
    """Regression: every .json and .png in bots_examples/ must load via
    load_starter_bot. The setup wizard surfaces these files to the
    user, so a regression in any one of them breaks the onboarding
    flow.

    Skipped automatically if the directory is missing so the test
    still works on a fresh clone that hasn't pulled fixtures yet.
    """
    base = Path(__file__).resolve().parent.parent / "bots_examples"
    if not base.is_dir():
        pytest.skip(f"bots_examples directory not found at {base}")

    artifacts = sorted(
        p
        for p in base.iterdir()
        if p.suffix.lower() in {".json", ".png"} and not p.name.startswith(".")
    )
    assert artifacts, "no starter artifacts found — wizard would be empty"

    failures: list[tuple[str, str]] = []
    for p in artifacts:
        try:
            data = load_starter_bot(p)
        except Exception as exc:
            failures.append((p.name, f"{type(exc).__name__}: {exc}"))
            continue
        # All four required fields must be non-empty for the wizard
        # to seed a usable bot.
        for field in REQUIRED_FIELDS:
            if not data.get(field):
                failures.append((p.name, f"empty {field!r} after load"))
                break

    if failures:
        details = "\n".join(f"  - {name}: {err}" for name, err in failures)
        pytest.fail(
            f"{len(failures)}/{len(artifacts)} starter artifacts failed to load:\n{details}"
        )
