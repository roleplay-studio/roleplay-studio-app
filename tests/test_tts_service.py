"""TDD red-phase tests for the TTS feature.

Coverage goal: lock down the public contract of the TTS port and service
BEFORE the implementation lands. If these tests pass, the contract is
stable enough to drive the implementation.

What's tested:

1. ``TTSProvider`` Protocol — concrete shape (synthesize -> audio bytes).
2. ``TTSService`` — content-hash-based disk cache: same (text, voice,
   model) -> same cache_id, second call hits cache without re-calling the
   provider.
3. ``TTSService.synthesize`` returns ``SynthesizeResult`` with cache_id
   that resolves via ``load_cached`` to the same bytes.
4. ``TTSService`` raises ``TTSError`` when the provider raises — no
   partial writes to disk.

These match the locked-down design (port protocol, service-level disk
cache, no silent schema migrations).
"""

from __future__ import annotations

import pytest

from app.application.services.tts import (
    SynthesizeResult,
    TTSError,
    TTSService,
)


class _FakeProvider:
    """In-memory deterministic TTS provider.

    Returns ``b"FAKE_MP3_" + text.encode()`` so test can correlate input
    and output without mocking whole ``httpx`` plumbing. Records every
    call so the cache test can assert the provider is hit only once.
    """

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[dict[str, object]] = []
        self._fail = fail

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        model: str,
        *,
        speed: float = 1.0,
    ) -> bytes:
        self.calls.append({"text": text, "voice": voice_id, "model": model, "speed": speed})
        if self._fail:
            raise RuntimeError("upstream boom")
        return ("FAKE_MP3_" + text).encode("utf-8")


@pytest.fixture
def provider() -> _FakeProvider:
    return _FakeProvider()


@pytest.fixture
def service(tmp_path, provider: _FakeProvider) -> TTSService:
    return TTSService(
        provider=provider,
        cache_dir=tmp_path / "tts",
        default_voice="voice-default",
        default_model="speech-02-turbo",
    )


@pytest.mark.asyncio
async def test_provider_protocol_is_callable(service: TTSService) -> None:
    """The port surface is just ``synthesize(...)``; everything else (caching,
    hashing, http transport) lives behind ``TTSService``.

    We duck-type against the protocol's required attributes rather
    than ``isinstance(...)`` because ``Protocol`` requires
    ``@runtime_checkable`` for that — the structural check is what
    matters here.
    """
    for name in ("synthesize",):
        assert callable(getattr(service.provider, name, None)), f"TTSProvider must expose {name}()"


@pytest.mark.asyncio
async def test_synthesize_returns_cache_id_and_audio(service: TTSService) -> None:
    result = await service.synthesize("hello")
    assert isinstance(result, SynthesizeResult)
    assert result.audio_bytes == b"FAKE_MP3_hello"
    # cache_id is what the route hands back to the client for the GET endpoint.
    assert isinstance(result.cache_id, str) and len(result.cache_id) >= 16
    assert result.from_cache is False


@pytest.mark.asyncio
async def test_second_call_hits_cache(service: TTSService) -> None:
    """Same (text, voice, model) -> same cache_id, provider hit exactly once."""
    first = await service.synthesize("repeat me")
    second = await service.synthesize("repeat me")

    assert first.cache_id == second.cache_id
    assert second.from_cache is True
    assert second.audio_bytes == first.audio_bytes
    assert len(service.provider.calls) == 1  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_cache_distinguishes_voice(tmp_path, provider: _FakeProvider) -> None:
    """Different voice -> different cache bucket (avoids same content spoken
    in two voices clobbering each other).
    """
    svc = TTSService(provider, tmp_path / "tts", "v1", "m1")
    a = await svc.synthesize("text", voice_id="v1")
    b = await svc.synthesize("text", voice_id="v2")
    assert a.cache_id != b.cache_id


@pytest.mark.asyncio
async def test_load_cached_round_trips(service: TTSService) -> None:
    """The cache_id handed to the client must round-trip via load_cached.
    This is the contract the /tts/audio/{id} endpoint depends on.
    """
    r = await service.synthesize("round trip")
    loaded = service.load_cached(r.cache_id)
    assert loaded == r.audio_bytes


@pytest.mark.asyncio
async def test_provider_failure_raises_tts_error(service: TTSService) -> None:
    """Provider failure must surface as ``TTSError`` and NOT pollute the
    cache (partial bytes must not be written).
    """
    failing = _FakeProvider(fail=True)
    bad = TTSService(failing, service.cache_dir, "v", "m")
    with pytest.raises(TTSError):
        await bad.synthesize("explode")
    # No files were created under cache_dir for that request.
    assert list(service.cache_dir.iterdir()) == []


@pytest.mark.asyncio
async def test_load_cached_missing_raises(tmp_path) -> None:
    svc = TTSService(_FakeProvider(), tmp_path / "tts", "v", "m")
    with pytest.raises(TTSError):
        svc.load_cached("nonexistent_cache_id_xxxxxxxxxxxxxxxxx")
