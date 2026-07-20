"""Tests for ``MiniMaxTTSProvider`` soft-failure envelopes.

When MiniMax returns HTTP 200 with ``base_resp.status_code != 0`` (e.g.
2049 "invalid api key", 2053 "quota exceeded") we surface the
underlying reason in the error message instead of falling through to
"missing data.audio". This locks the contract so any future refactor
that loses the message fails CI.

Uses ``respx``-style httpx mocking via the constructor's
``api_key_override`` path so we don't need a real MiniMax key to run
the tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.infrastructure.config import Settings
from app.infrastructure.tts import MiniMaxTTSProvider


class _MockTransport(httpx.AsyncBaseTransport):
    """Captures the request and returns a canned response."""

    def __init__(self, response_status: int, response_body: dict[str, Any] | str) -> None:
        self.response_status = response_status
        self.response_body = response_body
        self.last_request: httpx.Request | None = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.last_request = request
        if isinstance(self.response_body, str):
            return httpx.Response(self.response_status, content=self.response_body)
        return httpx.Response(self.response_status, json=self.response_body)


@pytest.fixture
def provider_settings(tmp_path: Path) -> Settings:
    """Settings with an *explicit* TTS_API_KEY so we never accidentally
    fall back to LLM_API_KEY in the test."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        db_path=str(tmp_path / "v.db"),
        tts_provider="minimax",
        tts_api_key="test-key-explicit",
    )


@pytest.fixture
async def provider(provider_settings: Settings):
    p = MiniMaxTTSProvider(settings=provider_settings)
    await p.startup()
    yield p
    await p.close()


async def test_base_resp_invalid_api_key_surfaces_clear_message(provider: MiniMaxTTSProvider) -> None:
    """status_code=2049 ("invalid api key") must reach the operator verbatim,
    not collapse to the generic "missing data.audio" fallthrough.

    Stub the real HTTP client with a transport that returns the
    canonical MiniMax soft-failure envelope so the test does not need
    a real key or sandbox.
    """
    p = provider
    p._client = httpx.AsyncClient(
        transport=_MockTransport(
            200,
            {
                "base_resp": {"status_code": 2049, "status_msg": "invalid api key"},
                # data may be missing, or carry audio=None, or carry
                # a stub dict. The provider must look at base_resp first.
                "data": {"audio": None, "status": 2049},
            },
        ),
        base_url="https://api.minimax.io/v1",
        timeout=httpx.Timeout(10.0),
    )
    # The provider raises a plain RuntimeError; ``TTSService.synthesize``
    # catches it and rewraps as ``TTSError``. We exercise the provider
    # directly here because the conversion logic lives in the service
    # layer (covered by tests/test_tts_service.py).
    with pytest.raises(RuntimeError) as excinfo:
        await p.synthesize("hello", "Russian_ReliableMan", "speech-02-turbo")
    msg = str(excinfo.value)
    assert "2049" in msg, f"status_code missing from error: {msg!r}"
    assert "invalid api key" in msg, f"status_msg missing from error: {msg!r}"


async def test_base_resp_success_returns_audio(provider_settings: Settings) -> None:
    """A normal envelope (status_code=0) with a hex audio payload must
    be decoded and returned. Locks the contract for the happy path
    even though the real provider keeps changing wrapper shapes.
    """
    p = MiniMaxTTSProvider(settings=provider_settings)
    await p.startup()
    try:
        # 4 hex bytes ("deadbeef") decoded = bytes([0xDE,0xAD,0xBE,0xEF]).
        transport = _MockTransport(
            200,
            {
                "base_resp": {"status_code": 0, "status_msg": ""},
                "data": {"audio": "deadbeef", "status": 1},
            },
        )
        p._client = httpx.AsyncClient(
            transport=transport,
            base_url="https://api.minimax.io/v1",
            timeout=httpx.Timeout(10.0),
        )
        result = await p.synthesize("hi", "Russian_ReliableMan", "speech-02-turbo")
        assert result == b"\xde\xad\xbe\xef"
        # Contract: provider must POST to the documented sync HTTP
        # endpoint and ask for hex-encoded audio. Without
        # ``output_format=hex`` MiniMax's sync route may return a
        # download URL instead of inline audio — which our parser
        # cannot handle and falls into the "missing data.audio"
        # branch. Locking the request shape prevents a future
        # refactor from silently regressing the integration.
        assert transport.last_request is not None
        assert transport.last_request.url.path == "/v1/t2a_v2"
        body = json.loads(transport.last_request.content)
        assert body["output_format"] == "hex", (
            f"sync MiniMax endpoint requires output_format=hex to return "
            f"inline audio; got body={body!r}"
        )
        assert body["stream"] is False
        assert body["voice_setting"]["voice_id"] == "Russian_ReliableMan"
        assert body["audio_setting"]["format"] == "mp3"
    finally:
        await p.close()
