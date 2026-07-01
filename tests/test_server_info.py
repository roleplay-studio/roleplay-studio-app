"""Tests for GET /api/server-info — discovery endpoint for Tauri
Android client."""

from fastapi.testclient import TestClient

from api.main import app


def test_server_info_returns_url_and_version():
    client = TestClient(app)
    res = client.get("/api/server-info")
    assert res.status_code == 200
    data = res.json()
    assert "url" in data
    assert data["url"].startswith("http")
    assert "version" in data
    assert isinstance(data["version"], str)
    # The version must come from package metadata (pyproject.toml),
    # not a hardcoded fallback. If this is "0.0.0+unknown" the
    # package is not installed at all.
    assert data["version"] != "0.0.0+unknown", (
        f"server_info returned {data['version']!r} — the package metadata "
        "could not be read; the previous hardcoded '0.1.0' fallback has "
        "been replaced with a real metadata lookup."
    )
    assert data["version"] == "0.1.0"


def test_server_info_no_auth_required():
    """Auth not implemented yet — endpoint must be reachable without
    Authorization header. Documents intent: any future auth must
    NOT apply to this discovery endpoint."""
    client = TestClient(app)
    # Explicitly send no Authorization header
    res = client.get("/api/server-info", headers={"Authorization": ""})
    assert res.status_code == 200


def test_server_info_no_token_field():
    """Auth not implemented yet — endpoint must NOT leak token data."""
    client = TestClient(app)
    res = client.get("/api/server-info")
    data = res.json()
    assert "has_token" not in data
    assert "token_hint" not in data
