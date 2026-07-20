"""TTS use case: synthesize + disk cache.

Layering
--------
* :class:`TTSProvider` (in ``app.application.ports``) — the abstract
  port. Two implementations in ``app.infrastructure``:

  * ``MiniMaxTTSProvider`` — production, talks to
    ``https://api.minimax.io/v1/t2a_v2``.
  * ``MockTTSProvider`` — returns a deterministic in-process MP3 stub
    for E2E tests and local dev without spending TTS credits.

* :class:`TTSService` — this module. Owns the disk cache and exposes a
  stable ``cache_id`` so the API layer can build a ``/tts/audio/<id>``
  endpoint that streams straight from disk.

Cache contract
--------------
* ``cache_id`` is ``sha256(model | voice_id | text)`` truncated to 16
  hex chars (64 bits) — collision-resistant enough for per-message
  audio. Same input -> same id, guaranteed. Different ``voice_id`` or
  ``model`` -> different id, so swapping voices never busts a cache
  that's stored under the old voice silently.
* Cache files live under ``ROLEPLAY_DATA_DIR/tts_cache/`` by default
  (``Settings.tts_cache_dir``). The dir is created on first write.
* Errors from the provider are rewrapped in :class:`TTSError` and
  **never** leave a partial file behind — we only ``.write_bytes``
  after the provider call returned successfully.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.application.exceptions import ExternalServiceError

if TYPE_CHECKING:
    from app.application.ports import TTSProvider


class TTSError(ExternalServiceError):
    """Any failure during TTS synthesis or cache lookup.

    Wraps provider failures (``httpx.HTTPError``, ``RuntimeError``,
    authentication errors) AND missing-cache-id lookups so callers
    only ever need to handle one exception type.
    """


@dataclass(frozen=True)
class SynthesizeResult:
    """What :meth:`TTSService.synthesize` returns.

    ``cache_id`` is what the API hands back to the client so the
    subsequent ``GET /tts/audio/{cache_id}`` can replay the bytes
    without re-calling the provider. ``audio_bytes`` is included for
    callers that want to stream directly without going through the
    GET endpoint (e.g. SSE, batch downloads). ``from_cache`` is True
    when the second call hit the cache and the provider was skipped.
    """

    audio_bytes: bytes
    cache_id: str
    from_cache: bool


def _cache_id(model: str, voice_id: str, text: str) -> str:
    """Stable 16-hex cache key for a (model, voice, text) triple.

    Uses ``|`` as a separator so e.g. ``model="speech"``,
    ``voice="02-turbo"`` can never collide with ``model="speech-02"``,
    ``voice="turbo"`` even on the unlikely hash collision.
    """
    h = hashlib.sha256(f"{model}|{voice_id}|{text}".encode()).hexdigest()
    return h[:16]


class TTSService:
    """Text-to-speech with disk caching.

    Single instance per process is fine — the service is stateless
    except for the cache directory it manages. ``provider`` is the
    only dependency; everything else (``cache_dir``, defaults) is
    configurable per-test / per-deployment.
    """

    def __init__(
        self,
        provider: TTSProvider,
        cache_dir: Path,
        default_voice: str,
        default_model: str,
    ) -> None:
        self._provider = provider
        self.cache_dir = cache_dir
        self._default_voice = default_voice
        self._default_model = default_model
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    # Public alias used by tests / route layer to introspect which
    # provider is wired in (debug endpoint, health check, etc.).
    @property
    def provider(self) -> TTSProvider:
        return self._provider

    async def synthesize(
        self,
        text: str,
        *,
        voice_id: str | None = None,
        model: str | None = None,
        speed: float = 1.0,
    ) -> SynthesizeResult:
        """Synthesize (or hit cache) and return audio + cache id.

        Defaults are applied lazily so the service stays cheap to
        construct and tests can pin specific voices.
        """
        resolved_voice = voice_id or self._default_voice
        resolved_model = model or self._default_model
        cid = _cache_id(resolved_model, resolved_voice, text)
        target = self.cache_dir / f"{cid}.mp3"
        if target.exists():
            return SynthesizeResult(
                audio_bytes=target.read_bytes(),
                cache_id=cid,
                from_cache=True,
            )
        try:
            audio = await self._provider.synthesize(
                text,
                resolved_voice,
                resolved_model,
                speed=speed,
            )
        except Exception as exc:
            raise TTSError(f"TTS provider failed: {exc}") from exc
        # Only persist after a successful provider call — partial
        # writes from a crashed request would otherwise leave zero-byte
        # files that hit the cache branch forever.
        target.write_bytes(audio)
        return SynthesizeResult(audio_bytes=audio, cache_id=cid, from_cache=False)

    def load_cached(self, cache_id: str) -> bytes:
        """Read the cached audio for ``cache_id`` or raise :class:`TTSError`.

        This is what the ``GET /tts/audio/{id}`` endpoint calls.
        Raises instead of returning ``None`` so the FastAPI route can
        turn it into a 404 via the existing error-handling stack.
        """
        target = self.cache_dir / f"{cache_id}.mp3"
        if not target.exists():
            raise TTSError(f"no cached audio for id={cache_id}")
        return target.read_bytes()
