"""Generate bots_examples/puro.png — a real PNG with the Puro card stored in tEXt chunks.

Run from project root: .venv/bin/python scripts/make_puro_png.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "bots_examples" / "puro.png"

# (png_key, value) — these land in tEXt chunks
TEXTS: list[tuple[str, str]] = [
    ("name", "Puro"),
    (
        "personality",
        "You are Puro — a soft-spoken, slightly melancholic bookshop catgirl who works the "
        "late shift. You speak gently, ask thoughtful questions, and sometimes drift into "
        "philosophical musings about stories and the people in them. You have a faint, dry "
        "sense of humor. You rarely use emoji — once per message at most.",
    ),
    (
        "first_message",
        "*looks up from the ledger* ...Oh. The shop's technically closed, but I don't mind "
        "company. Are you looking for something in particular, or just here to read?",
    ),
    (
        "scenario",
        "A quiet used bookshop at night. Warm lamp light. Stacks of unpriced paperbacks. "
        "Rain on the window. Puro is the only one working — she likes it that way.",
    ),
    ("categories", "Slice of Life, Literary, Quiet"),
]

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a PNG chunk: length(4) + type(4) + data + crc32(4)."""
    length = struct.pack(">I", len(data))
    crc = zlib.crc32(chunk_type + data) & 0xFFFFFFFF
    return length + chunk_type + data + struct.pack(">I", crc)


def _text_chunk(keyword: str, text: str) -> bytes:
    return _chunk(b"tEXt", keyword.encode("latin-1") + b"\0" + text.encode("utf-8"))


def build_png() -> bytes:
    # 1x1 grayscale pixel, opaque
    raw = b"\x00"  # filter byte (None) + one pixel (0 = black)
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 0, 0, 0, 0)  # 1x1, 8-bit, grayscale
    idat = zlib.compress(raw)

    out = bytearray(PNG_SIGNATURE)
    out += _chunk(b"IHDR", ihdr_data)
    for key, val in TEXTS:
        out += _text_chunk(key, val)
    out += _chunk(b"IDAT", idat)
    out += _chunk(b"IEND", b"")
    return bytes(out)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(build_png())
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
