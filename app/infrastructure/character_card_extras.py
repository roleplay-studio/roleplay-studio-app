"""Helpers for character card export (placeholder avatar generation)."""

from __future__ import annotations

import hashlib
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


def generate_placeholder_png(name: str, size: int = 512) -> bytes:
    """Generate a 512x512 gradient PNG as a placeholder avatar.

    Colors are derived from ``sha256(name)`` so the same name always
    produces the same image. The first letter of ``name`` is centered
    in white over the gradient.
    """
    digest = hashlib.sha256(name.encode()).digest()
    color1 = (digest[0], digest[1], digest[2])
    color2 = (digest[3], digest[4], digest[5])
    img = Image.new("RGB", (size, size), color1)
    draw = ImageDraw.Draw(img)
    for y in range(size):
        ratio = y / size
        r = int(color1[0] * (1 - ratio) + color2[0] * ratio)
        g = int(color1[1] * (1 - ratio) + color2[1] * ratio)
        b = int(color1[2] * (1 - ratio) + color2[2] * ratio)
        draw.line([(0, y), (size, y)], fill=(r, g, b))
    try:
        font = ImageFont.truetype("Arial.ttf", size // 3)
    except OSError:
        font = ImageFont.load_default()
    letter = name[:1].upper() if name else "?"
    draw.text((size // 2, size // 2), letter, fill="white", anchor="mm", font=font)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
