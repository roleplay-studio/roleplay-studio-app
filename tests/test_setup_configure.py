"""API-level validation for the SetupWizard's ``/configure`` route.

Before Phase 4, the route accepted any string for ``provider`` and
dumped it into the .env file via ``set_key``. The frontend couldn't
end up here with a bad id today (it ships a hard-coded list), but a
custom-http client or a stale browser could. This test pins the
behaviour: unknown ids must surface as a 4xx, not a 200 with a
silent fallback to mock at process boot.

We don't exercise the side-effects (``set_key`` writes to a real
``.env`` file) — those are covered by the existing happy-path smoke
tests. This suite focuses on the rejection contract.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.constants import PROVIDERS
from api.deps import _get_container
from api.main import app


class _NoopContainer:
    """Minimal stand-in satisfying whatever setup_status needs during the test.

    Looking at ``api/routes/setup.py:32`` (``setup_status``) we need a
    ``container`` with a ``bots`` attribute whose ``list_bots`` returns
    an awaitable iterable of length zero. Everything else in the route
    is pure settings-from-env — we don't care about it here.
    """

    class _Bots:
        async def list_bots(self) -> list[Any]:
            return []

    bots = _Bots()


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path) -> Iterator[TestClient]:
    """Isolated TestClient — overrides DI, redirects .env writes to tmp_path."""
    # Direct the route's data_dir at tmp_path so it doesn't touch the
    # real .env file (or create one in cwd). ``data_dir`` in the route
    # honours ``ROLEPLAY_DATA_DIR`` from env, so we set it.
    monkeypatch.setenv("ROLEPLAY_DATA_DIR", str(tmp_path))
    app.dependency_overrides[_get_container] = lambda: _NoopContainer()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _payload(provider: str, **overrides) -> dict[str, Any]:
    """Build a valid ConfigureRequest body that overrides ``provider``."""
    body = {
        "provider": "openrouter",
        "base_url": "",
        "api_key": "",
        "chat_model": "",
    }
    body.update(overrides)
    body["provider"] = provider
    return body


def test_configure_accepts_every_providers_id(client: TestClient) -> None:
    """Every key in api.constants.PROVIDERS + 'mock' produces a 200."""
    with patch("api.routes.setup.set_key"):
        for pid in (*PROVIDERS.keys(), "mock"):
            resp = client.post("/api/setup/configure", json=_payload(pid))
            assert resp.status_code == 200, (
                f"provider={pid!r} returned {resp.status_code}: {resp.text}"
            )


def test_configure_rejects_unknown_provider(client: TestClient) -> None:
    """Unknown provider ids are rejected with a 4xx, not silently
    accepted (which used to put a bad id in .env and crash on next
    boot via the pre-Phase-1 Settings Literal)."""
    resp = client.post(
        "/api/setup/configure",
        json=_payload("definitely-not-a-real-provider"),
    )
    assert 400 <= resp.status_code < 500, (
        f"expected 4xx for unknown provider, got {resp.status_code}: {resp.text}"
    )


def test_configure_accepts_mock(client: TestClient) -> None:
    """'mock' is special-cased — not in PROVIDERS but a valid id for
    E2E / CI. The route must accept it the same way Settings does."""
    with patch("api.routes.setup.set_key"):
        resp = client.post("/api/setup/configure", json=_payload("mock"))
        assert resp.status_code == 200


def test_configure_rejects_empty_provider(client: TestClient) -> None:
    """Defence: an empty provider string should fail before reaching
    ``set_key``. Empty strings used to leak through to .env as
    ``LLM_PROVIDER=`` and crash the very next Settings() with a
    confusing validation error."""
    resp = client.post("/api/setup/configure", json=_payload(""))
    assert 400 <= resp.status_code < 500


def test_configure_providers_endpoint_returns_consistent_set(client: TestClient) -> None:
    """/providers already exists — verify it still works and includes every key from the registry."""
    resp = client.get("/api/setup/providers")
    assert resp.status_code == 200
    listed_ids = {p["id"] for p in resp.json()}
    assert set(PROVIDERS.keys()) <= listed_ids, (
        f"missing from /providers: {set(PROVIDERS.keys()) - listed_ids}"
    )
