"""Tests for `python -m scripts.print_qr` CLI."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

# Use the venv's python so subprocess has access to project deps
# (uv runs pytest with the system python but sets VIRTUAL_ENV).
_PYTHON = (
    os.path.join(os.environ["VIRTUAL_ENV"], "bin", "python")
    if os.environ.get("VIRTUAL_ENV")
    else sys.executable
)


def test_print_qr_generates_png_file():
    with tempfile.TemporaryDirectory() as tmp:
        out_path = Path(tmp) / "qr.png"
        result = subprocess.run(
            [
                _PYTHON,
                "-m",
                "scripts.print_qr",
                "--url",
                "https://test.example.com",
                "--out",
                str(out_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert out_path.exists()
        assert out_path.stat().st_size > 100  # valid PNG, not empty
        # PNG magic bytes
        with open(out_path, "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_print_qr_uses_env_url_when_not_specified(tmp_path, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://env.example.com")
    out_path = tmp_path / "qr.png"
    result = subprocess.run(
        [_PYTHON, "-m", "scripts.print_qr", "--out", str(out_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert out_path.exists()
