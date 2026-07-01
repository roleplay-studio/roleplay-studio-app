"""Image processing utilities for avatar uploads."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

# Thumbnail sizes: (width, suffix)
AVATAR_SIZES: list[tuple[int, str]] = [
    (500, "_500"),
    (200, "_200"),
    (50, "_50"),
]


def constrain_image(
    source_path: str | Path,
    dest_path: str | Path,
    max_dim: int = 1024,
    *,
    quality: int = 85,
) -> tuple[int, int]:
    """Resize image if it exceeds max_dim, save to dest_path.

    Returns the resulting (width, height).
    """
    img = Image.open(source_path)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    w, h = img.size
    if w > max_dim or h > max_dim:
        ratio = max_dim / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    ext = str(dest_path).rsplit(".", 1)[-1].lower()
    save_kwargs: dict = {}
    if ext in ("jpg", "jpeg"):
        save_kwargs["quality"] = quality
        save_kwargs["optimize"] = True
    elif ext == "webp":
        save_kwargs["quality"] = quality

    Path(dest_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(dest_path, **save_kwargs)
    result = img.size
    img.close()
    return result


def resize_avatar(
    source_path: str | Path,
    dest_dir: str | Path,
    stem: str,
    ext: str,
    *,
    sizes: list[tuple[int, str]] | None = None,
) -> dict[int, str]:
    """Resize an avatar image to multiple widths, saving as separate files.

    Args:
        source_path: Path to the original uploaded image.
        dest_dir: Directory to save resized images.
        stem: Filename stem (e.g. uuid hex).
        ext: File extension including dot (e.g. ".png").
        sizes: Override default sizes. Each tuple is (max_width, suffix).

    Returns:
        Dict mapping width -> absolute file path for each resized version.
    """
    sizes = sizes or AVATAR_SIZES
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    results: dict[int, str] = {}

    try:
        img = Image.open(source_path)
    except Exception:
        logger.exception("Failed to open image: %s", source_path)
        return results

    # Convert to RGB for JPEG compatibility (handles PNG with alpha, etc.)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGB")

    orig_w, orig_h = img.size

    for max_width, suffix in sizes:
        if orig_w <= max_width and orig_h <= max_width:
            resized = img.copy()
        else:
            ratio = max_width / max(orig_w, orig_h)
            new_w = int(orig_w * ratio)
            new_h = int(orig_h * ratio)
            resized = img.resize((new_w, new_h), Image.LANCZOS)

        filename = f"{stem}{suffix}{ext}"
        out_path = dest_dir / filename

        save_kwargs: dict = {}
        if ext.lower() in (".jpg", ".jpeg"):
            save_kwargs["quality"] = 85
            save_kwargs["optimize"] = True
        elif ext.lower() == ".webp":
            save_kwargs["quality"] = 85

        resized.save(out_path, **save_kwargs)
        results[max_width] = str(out_path)
        logger.debug("Saved avatar %s (%dx%d)", filename, resized.size[0], resized.size[1])

    img.close()
    return results
