"""Tests for image resizing utilities."""

from __future__ import annotations

import os
import tempfile

from PIL import Image

from app.infrastructure.image_utils import constrain_image, resize_avatar


def _make_image(width: int, height: int, color: str = "red") -> str:
    """Create a temporary test image and return its path."""
    img = Image.new("RGB", (width, height), color=color)
    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    img.save(tmp.name)
    return tmp.name


class TestConstrainImage:
    def test_large_image_resized(self):
        source = _make_image(2000, 1500)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                dest = os.path.join(tmpdir, "out.png")
                w, h = constrain_image(source, dest, max_dim=1024)
                assert w == 1024
                assert h == 768
                assert os.path.exists(dest)
        finally:
            os.unlink(source)

    def test_small_image_unchanged(self):
        source = _make_image(800, 600)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                dest = os.path.join(tmpdir, "out.png")
                w, h = constrain_image(source, dest, max_dim=1024)
                assert w == 800
                assert h == 600
        finally:
            os.unlink(source)

    def test_overwrites_original(self):
        """constrain_image can overwrite the source file."""
        source = _make_image(2000, 2000)
        try:
            w, h = constrain_image(source, source, max_dim=1024)
            assert w == 1024
            assert h == 1024
            img = Image.open(source)
            assert img.size == (1024, 1024)
            img.close()
        finally:
            os.unlink(source)


class TestResizeAvatar:
    def test_resize_large_image(self):
        """Large image should be resized to all target sizes."""
        source = _make_image(1000, 800)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results = resize_avatar(source, tmpdir, "test", ".png")

                assert 500 in results
                assert 200 in results
                assert 50 in results

                # Check dimensions
                img500 = Image.open(results[500])
                assert img500.size[0] == 500
                assert img500.size[1] == 400  # proportional

                img200 = Image.open(results[200])
                assert img200.size[0] == 200
                assert img200.size[1] == 160

                img50 = Image.open(results[50])
                assert img50.size[0] == 50
                assert img50.size[1] == 40
        finally:
            os.unlink(source)

    def test_small_image_not_upscaled(self):
        """Images smaller than target should not be upscaled."""
        source = _make_image(30, 30)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results = resize_avatar(source, tmpdir, "small", ".png")

                # All versions should be 30x30 (original size)
                for width in [500, 200, 50]:
                    assert width in results
                    img = Image.open(results[width])
                    assert img.size == (30, 30)
        finally:
            os.unlink(source)

    def test_preserves_aspect_ratio(self):
        """Non-square images should maintain aspect ratio."""
        source = _make_image(1000, 500)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results = resize_avatar(source, tmpdir, "wide", ".png")

                img500 = Image.open(results[500])
                assert img500.size == (500, 250)  # 2:1 ratio preserved

                img200 = Image.open(results[200])
                assert img200.size == (200, 100)
        finally:
            os.unlink(source)

    def test_portrait_image(self):
        """Portrait images should resize correctly."""
        source = _make_image(400, 1200)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results = resize_avatar(source, tmpdir, "tall", ".png")

                img500 = Image.open(results[500])
                # max dimension = 1200, ratio = 500/1200 ≈ 0.417
                assert img500.size[1] == 500  # height is the max
                assert 166 <= img500.size[0] <= 167  # 400 * 500/1200 (rounding)
        finally:
            os.unlink(source)

    def test_jpeg_output(self):
        """JPEG files should be saved with quality optimization."""
        source = _make_image(800, 600)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results = resize_avatar(source, tmpdir, "photo", ".jpg")

                assert 500 in results
                assert results[500].endswith(".jpg")

                img = Image.open(results[500])
                assert img.size[0] == 500
        finally:
            os.unlink(source)

    def test_rgba_image_converted_to_rgb(self):
        """PNG with alpha channel should be converted for JPEG compat."""
        img = Image.new("RGBA", (800, 600), color=(255, 0, 0, 128))
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        img.save(tmp.name)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results = resize_avatar(tmp.name, tmpdir, "alpha", ".png")
                assert 500 in results

                result_img = Image.open(results[500])
                assert result_img.mode == "RGB"
        finally:
            os.unlink(tmp.name)

    def test_files_actually_created(self):
        """All returned paths should point to existing files."""
        source = _make_image(1000, 1000)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                results = resize_avatar(source, tmpdir, "exists", ".png")

                for width, path in results.items():
                    assert os.path.exists(path), f"File not found for {width}px: {path}"
                    assert os.path.getsize(path) > 0
        finally:
            os.unlink(source)

    def test_custom_sizes(self):
        """Custom size list should be respected."""
        source = _make_image(1000, 1000)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                custom = [(300, "_300"), (100, "_100")]
                results = resize_avatar(source, tmpdir, "custom", ".png", sizes=custom)

                assert 300 in results
                assert 100 in results
                assert 500 not in results  # default sizes not used
        finally:
            os.unlink(source)
