"""Integration tests for the TTS route.

Exercises the full container -> service -> provider -> cache -> HTTP
stack via ``TestClient``. Each test builds a fresh container with the
``mock`` TTS provider so we hit the cache layer without spending real
TTS credits.

Covers:

* 503 when TTS is disabled (the default ``Settings.tts_provider``).
* POST /synthesize round-trip with the mock provider.
* GET /audio/<id> streams the cached MP3 with the right headers.
* Cache hit: same input -> same cache_id, second call returns
  ``from_cache=true``.
* GET /audio/<id> returns 404 for an unknown id.

Uses the same ``dependency_overrides[_get_container]`` pattern as the
other route tests (see ``test_api.py``).
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.deps import _get_container
from api.main import create_app
from app.bootstrap import build_container
from app.infrastructure.config import Settings


@pytest.fixture
def tts_app(tmp_path: Path) -> Generator[TestClient]:
    """TestClient backed by a container with TTS_PROVIDER=mock.

    The ``mock`` provider synthesises a tiny stub MP3 and stores it
    in the per-test cache directory, so each test gets a clean
    disk cache but the rest of the wiring (route -> service -> disk
    -> bytes) is real.
    """
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg] — pydantic-settings kwarg
        db_path=str(tmp_path / "v.db"),
        tts_provider="mock",
        tts_cache_dir=str(tmp_path / "tts_cache"),
    )
    container = build_container(settings=settings)
    assert container.tts is not None, "mock provider should be wired in"

    app = create_app()
    app.dependency_overrides[_get_container] = lambda: container
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def disabled_app(tmp_path: Path) -> Generator[TestClient]:
    """TestClient backed by a container with ``TTS_PROVIDER=disabled``.

    Forces ``tts_provider="disabled"`` explicitly so the fixture works
    regardless of what the user has in their local ``.env`` — under a
    real MiniMax key the default container would not raise 503, and the
    test would fail for the wrong reason.
    """
    settings = Settings(
        _env_file=None,  # type: ignore[call-arg]
        db_path=str(tmp_path / "v.db"),
        tts_provider="disabled",
    )
    container = build_container(settings=settings)
    assert container.tts is None, "fixture must yield a TTS-less container"

    app = create_app()
    app.dependency_overrides[_get_container] = lambda: container
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()


def test_synthesize_returns_cache_id_and_audio_url(tts_app: TestClient) -> None:
    resp = tts_app.post("/api/tts/synthesize", json={"text": "hello world"})
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert len(data["cache_id"]) == 16
    assert data["cache_id"].isalnum()
    assert data["from_cache"] is False
    assert data["audio_url"] == f"/api/tts/audio/{data['cache_id']}"


def test_second_synthesize_hits_cache(tts_app: TestClient) -> None:
    first = tts_app.post("/api/tts/synthesize", json={"text": "repeat this"})
    second = tts_app.post("/api/tts/synthesize", json={"text": "repeat this"})
    assert first.json()["cache_id"] == second.json()["cache_id"]
    assert second.json()["from_cache"] is True


def test_get_audio_returns_mp3_bytes(tts_app: TestClient) -> None:
    cid = tts_app.post("/api/tts/synthesize", json={"text": "stream me"}).json()["cache_id"]
    resp = tts_app.get(f"/api/tts/audio/{cid}")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("audio/mpeg")
    # Mock provider writes "ID3" + body bytes; leading bytes confirm
    # the cache file landed where the GET endpoint reads it.
    assert resp.content[:3] == b"ID3"


def test_get_audio_unknown_id_returns_404(tts_app: TestClient) -> None:
    resp = tts_app.get("/api/tts/audio/0123456789abcdef")
    assert resp.status_code == 404


def test_get_audio_rejects_bad_format(tts_app: TestClient) -> None:
    resp = tts_app.get("/api/tts/audio/not-hex-123abc")  # length != 16
    assert resp.status_code == 400


def test_synthesize_rejects_empty_text(tts_app: TestClient) -> None:
    resp = tts_app.post("/api/tts/synthesize", json={"text": ""})
    assert resp.status_code == 422


def test_synthesize_disabled_returns_503(disabled_app: TestClient) -> None:
    """End-to-end test of the opt-in path: with the default (disabled)
    ``tts_provider``, both endpoints return 503.
    """
    assert disabled_app.post("/api/tts/synthesize", json={"text": "x"}).status_code == 503
    assert disabled_app.get("/api/tts/audio/0123456789abcdef").status_code == 503
