"""Regression: the bot export endpoint must embed the bot's avatar, not a
placeholder. The earlier bug was in the path construction — the route
appended an extra "avatars" segment to UPLOADS_DIR (which is already
the avatars directory), so the avatar file was looked up at
``uploads/avatars/avatars/<name>`` instead of ``uploads/avatars/<name>``
and never found, causing the export to fall back to a generated
placeholder.
"""

import inspect


def test_export_bot_does_not_double_up_avatars_dir():
    """export_bot must not append 'avatars' to UPLOADS_DIR.

    UPLOADS_DIR is already the avatars directory (api/constants.py
    builds the path as ``<project>/uploads/avatars``). Appending
    "avatars" again produces ``<project>/uploads/avatars/avatars/``,
    where avatar files never live, and the export silently falls
    back to a placeholder.
    """
    from api.routes import bots as bots_route

    source = inspect.getsource(bots_route.export_bot)
    # Look for the actual call site — should be ``Path(UPLOADS_DIR)``
    # with no trailing "avatars" segment.
    assert 'Path(UPLOADS_DIR) / "avatars"' not in source, (
        "export_bot is still appending 'avatars' to UPLOADS_DIR. "
        "UPLOADS_DIR already ends in /avatars, so this lookup path "
        "is wrong by one segment and the export silently falls back "
        "to a generated placeholder instead of the bot's avatar."
    )


def test_get_avatar_png_reads_from_correct_dir(tmp_path):
    """Pure unit test for _get_avatar_png: given a bot whose avatar_path
    is a public URL like ``/uploads/avatars/abc123.png`` and an
    ``avatar_dir`` that points at the real on-disk avatars directory
    containing that file, _get_avatar_png must return the file bytes
    rather than the placeholder.
    """
    from api.routes.bots import _get_avatar_png

    # Lay down a fake avatar in tmp_path/avatars/
    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir()
    fake_bytes = b"\x89PNG\r\n\x1a\n" + b"FAKE_AVATAR_PAYLOAD"
    avatar_path = avatar_dir / "abc123.png"
    avatar_path.write_bytes(fake_bytes)

    class _FakeBot:
        # The public path is what gets stored in bot.avatar_path
        # (see api/routes/bots.py:79: f"/uploads/avatars/{unique_name}")
        avatar_path = "/uploads/avatars/abc123.png"
        name = "TestBot"

    out = _get_avatar_png(_FakeBot(), avatar_dir)
    assert out == fake_bytes, (
        f"_get_avatar_png returned {out!r} instead of the avatar "
        f"bytes — it likely fell back to the placeholder."
    )


def test_get_avatar_png_falls_back_to_placeholder_when_missing(tmp_path):
    """If the avatar file does not exist on disk, _get_avatar_png must
    fall back to a generated placeholder rather than crash."""
    from api.routes.bots import _get_avatar_png

    avatar_dir = tmp_path / "avatars"
    avatar_dir.mkdir()

    class _FakeBot:
        avatar_path = "/uploads/avatars/missing.png"
        name = "NoAvatarBot"

    out = _get_avatar_png(_FakeBot(), avatar_dir)
    # Placeholder is a valid PNG; check the magic bytes.
    assert out.startswith(b"\x89PNG"), (
        f"Expected a generated PNG placeholder when the avatar file is missing, got {out[:8]!r}"
    )


def test_get_avatar_png_handles_no_avatar_path(tmp_path):
    """If the bot has no avatar_path at all, we still get a placeholder."""
    from api.routes.bots import _get_avatar_png

    class _FakeBot:
        avatar_path = None
        name = "BareBot"

    out = _get_avatar_png(_FakeBot(), tmp_path)
    assert out.startswith(b"\x89PNG")
