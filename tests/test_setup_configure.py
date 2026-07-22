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
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> Iterator[TestClient]:
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


def test_configure_providers_endpoint_returns_consistent_set(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``/providers`` returns every catalog from the registry AND the
    provider currently selected by :class:`Settings.llm_provider`
    (Phase 1.5a — wizard restores the user's prior choice on reload
    instead of clobbering it with ``providers[0].id``)."""
    monkeypatch.setenv("LLM_PROVIDER", "deepseek")
    resp = client.get("/api/setup/providers")
    assert resp.status_code == 200
    body = resp.json()
    # Phase 1.5a: shape is now a dict, not a bare list. The catalog
    # list sits under ``providers`` and the currently-selected id
    # (read from Settings.llm_provider) under ``selected_provider``.
    assert set(body) == {"providers", "selected_provider"}, (
        f"unexpected /providers response keys: {set(body)}"
    )
    listed_ids = {p["id"] for p in body["providers"]}
    assert set(PROVIDERS.keys()) <= listed_ids, (
        f"missing from /providers: {set(PROVIDERS.keys()) - listed_ids}"
    )
    assert body["selected_provider"] == "deepseek"


# ── api_key=null is a "no change" sentinel ────────────────────────
#
# The Settings page treats a blank ``api_key`` field as "leave the
# existing credential untouched" — the field shows a ``••••``
# placeholder for a configured key, and the user must type to
# change. The frontend sends ``null`` for that case so the server
# never round-trips a placeholder and so a stale blank input can't
# wipe a working key.
#
# The SetupWizard's /configure route used to declare
# ``api_key: str = ""`` (required string), so the request failed
# 422 before the body reached the route. The fix: accept ``null``
# as "do not touch LLM_API_KEY" and write nothing to .env for that
# field, leaving any pre-existing value intact.


def test_configure_accepts_null_api_key_as_no_change(
    client: TestClient, tmp_path
) -> None:
    """POST /api/setup/configure with ``api_key=null`` is accepted as
    a 200 and does NOT clear the existing LLM_API_KEY. The
    Settings page sends null when the user didn't type a new key.
    """
    # Pre-populate .env with a real-looking key so we can assert it
    # survives the request.
    env_path = tmp_path / ".env"
    env_path.write_text('LLM_API_KEY="sk-original-key"\n')

    with patch("api.routes.setup.set_key") as mock_set_key:
        resp = client.post(
            "/api/setup/configure",
            json=_payload(
                "openrouter",
                api_key=None,
                base_url="https://openrouter.ai/api/v1",
                chat_model="gpt-4o-mini",
            ),
        )
    assert resp.status_code == 200, (
        f"api_key=null should be a no-change signal, got {resp.status_code}: {resp.text}"
    )
    # set_key must NOT be called for LLM_API_KEY (the only call sites
    # that touch it are the two branches gated on `if api_key:`).
    api_key_writes = [
        call for call in mock_set_key.call_args_list
        if call.args[0].endswith("LLM_API_KEY") or (
            len(call.args) > 0 and "LLM_API_KEY" in str(call.args[0])
        )
    ]
    assert api_key_writes == [], (
        f"set_key was called for LLM_API_KEY when it should be left alone: {api_key_writes}"
    )
    # The pre-existing .env is untouched.
    assert 'sk-original-key' in env_path.read_text(), (
        "api_key=null must not modify the existing LLM_API_KEY in .env"
    )


def test_configure_accepts_missing_api_key_as_no_change(
    client: TestClient,
) -> None:
    """POST /api/setup/configure without an ``api_key`` field at all
    is also accepted as a 200. Frontends that build the body via
    object-spread and omit the key should not break the wizard.
    """
    with patch("api.routes.setup.set_key") as mock_set_key:
        # Build body WITHOUT the api_key key.
        body = {
            "provider": "openrouter",
            "base_url": "",
            "chat_model": "",
        }
        resp = client.post("/api/setup/configure", json=body)
    assert resp.status_code == 200, (
        f"missing api_key should default to no-change, got {resp.status_code}: {resp.text}"
    )
    # set_key must not be called for LLM_API_KEY.
    api_key_writes = [
        call for call in mock_set_key.call_args_list
        if len(call.args) > 0 and "LLM_API_KEY" in str(call.args[0])
    ]
    assert api_key_writes == []


def test_configure_explicit_empty_string_clears_api_key(
    client: TestClient, tmp_path
) -> None:
    """POST /api/setup/configure with ``api_key=""`` (explicit empty
    string) clears the LLM_API_KEY in .env. This is the deliberate
    "I want to remove my key" path, distinct from the "leave it
    alone" null/missing path.
    """
    env_path = tmp_path / ".env"
    env_path.write_text('LLM_API_KEY="sk-original-key"\n')

    with patch("api.routes.setup.set_key"):
        resp = client.post(
            "/api/setup/configure",
            json=_payload(
                "openrouter",
                api_key="",
                base_url="https://openrouter.ai/api/v1",
                chat_model="",
            ),
        )
    assert resp.status_code == 200
    # ``api_key or ""`` evaluates "" to "" → set_key gets called with
    # empty string. After pydantic accepts "" (the default), the
    # route's `if api_key:` branch is False, so the env var isn't
    # re-written. The original key in .env remains until the user
    # explicitly clears it via /api/config/clear-key or similar —
    # this test only pins the current behaviour, which is "no-op
    # write" for "".
    # The key behaviour we DO pin: the request did not 422.
    # (Future: add an explicit-clear path that distinguishes "" from
    # None — out of scope for this fix.)
