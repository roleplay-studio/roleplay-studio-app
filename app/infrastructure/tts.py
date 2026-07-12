"""Infrastructure adapters for the text-to-speech port.

Two implementations of ``TTSProvider`` (defined in ``app.application.ports``):

* :class:`MiniMaxTTSProvider` — talks to ``https://api.minimaxi.com/v1/t2a_v2``
  over HTTPS via ``httpx``. Production path; requires
  ``TTS_PROVIDER=minimax`` plus ``TTS_API_KEY`` (or ``LLM_API_KEY`` fallback).
* :class:`MockTTSProvider` — in-process deterministic simulator that returns
  a tiny synthetic MP3 stub so dev / E2E suites can exercise the
  synthesize -> cache -> GET pipeline without spending TTS credits.

Wire choice happens in ``app.bootstrap.build_container`` driven by
``Settings.tts_provider``. ``disabled`` is handled upstream — it
means we never construct any provider, and the route returns 503 so
the frontend hides the play button.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass

import httpx

from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MiniMax provider
# ---------------------------------------------------------------------------

#: Hard timeout for one T2A call. MiniMax latency in practice is well
#: under 10 s on long inputs; 30 s leaves headroom for the prompt
#: audio sometimes used in /v1/t2a_v2 (we don't pass prompt audio, but
#: cold-start + large body can spike).
_REQUEST_TIMEOUT_S = 30.0


@dataclass(frozen=True)
class MiniMaxTTSResponse:
    """What ``/v1/t2a_v2`` returns on success.

    MiniMax emits a hex-encoded MP3 payload in ``data.audio`` by default
    (alternatively a URL when ``stream=true``, which we don't use). We
    handle the hex case here; the URL case is rejected explicitly
    because it would require an extra hop.

    Kept as a separate dataclass so a future "stream=true" path can
    be slotted in without churning the rest of the file.
    """

    audio_hex: str
    audio_format: str


class MiniMaxTTSProvider:
    """HTTP client for ``https://api.minimaxi.com/v1/t2a_v2``.

    Matches the ``TTSProvider`` protocol surface (see
    ``app.application.ports``). Lifecycle follows the LLM pattern:
    ``__init__`` is lazy, ``startup`` opens the httpx client,
    ``close`` shuts it. The FastAPI lifespan handler wires these up
    alongside the chat LLM so a single ``shutdown_llms`` call covers
    everything.

    Config / Settings
    -----------------
    * ``base_url`` — overridable for proxies / private deployments.
    * ``api_key`` — ``SecretStr`` from settings; ``get_secret_value()``
      gets the raw bearer token for the Authorization header.
    * ``voice_id``, ``model``, ``speed`` — passed into the body verbatim.

    The endpoint is documented in the MiniMax API reference; the
    payload schema we emit (model + voice_id + audio settings + text)
    matches their v2 "t2a_v2" specification. Operators can swap voice
    and model freely via Settings without code changes.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        api_key_override: str | None = None,
        base_url_override: str | None = None,
    ) -> None:
        self.settings = settings
        # ``effective_tts_api_key`` falls back to ``llm_api_key`` so an
        # operator with a single MiniMax key covering chat+TTS doesn't
        # have to duplicate it. ``api_key_override`` is the escape hatch
        # for tests that build the provider without going through Settings.
        key = api_key_override
        if key is None:
            eff = settings.effective_tts_api_key
            key = eff.get_secret_value() if eff is not None else None
        if not key:
            raise ValueError("TTS_API_KEY (or LLM_API_KEY) is required for MiniMaxTTSProvider")
        self._api_key = key
        self._base_url = (base_url_override or settings.tts_base_url).rstrip("/")
        self._client: httpx.AsyncClient | None = None

    async def startup(self) -> None:
        """Open the httpx client. Idempotent — pair with ``close()``.

        Earlier versions ``del self._api_key``-ed the SecretStr here
        thinking the static-typer would complain about an unused
        private attribute. That worked once (the attribute was read
        synchronously on the very first ``synthesize`` call) but the
        SecretStr was missing by the time the lifespan re-ran
        ``startup`` / ``close`` round-trips, so any subsequent call
        blew up with ``AttributeError: '_api_key'`` — exactly the
        502 the user saw in production. We keep the attribute, and
        ``_request_headers`` reads it on every request.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_S)

    async def close(self) -> None:
        """Close the httpx client. Safe to call on an un-started instance."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        model: str,
        *,
        speed: float = 1.0,
    ) -> bytes:
        """Call ``/t2a_v2`` and return decoded MP3 bytes.

        Raises:
            RuntimeError: on transport failure, non-2xx status, or
                unexpected response shape. ``TTSService`` rewraps this
                as :class:`TTSError` so the route only ever sees one
                exception type.
        """
        if self._client is None:
            raise RuntimeError("MiniMaxTTSProvider used before startup()")
        url = f"{self._base_url}/t2a_v2"
        body = {
            "model": model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice_id,
                "speed": float(speed),
                "vol": 1.0,
                "pitch": 0,
            },
            "audio_setting": {
                "sample_rate": 32000,
                "bitrate": 128000,
                "format": "mp3",
                "channel": 1,
            },
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            # MiniMax uses these two header slots for their own
            # usage-tracking identity fields. Defaults are harmless
            # in our context — operators can override via an
            # ``api_key_override``-based provider if they need to
            # identify their integration specifically.
            "GroupId": "roleplay-studio",
        }
        try:
            resp = await self._client.post(url, json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise RuntimeError(f"TTS transport error: {exc}") from exc
        if resp.status_code >= 400:
            # MiniMax returns JSON envelopes with a ``message`` field on
            # errors; expose that text in the wrapped exception so logs
            # carry the operator-visible reason (not just a status code).
            snippet = resp.text[:200]
            _dump_raw_response("minimax", f"http_{resp.status_code}", resp, resp.text)
            raise RuntimeError(f"TTS provider {resp.status_code}: {snippet}")
        # Validate the JSON envelope **before** the audio-decode path so
        # the user sees a meaningful "what did MiniMax return" message
        # rather than a downstream ValueError from bytes.fromhex("").
        # Common causes for the 200-but-empty case: model requires a
        # different voice_id than the one we sent, billing/quota
        # exhaustion, or a region-only authentication scope.
        try:
            peek = resp.json()
        except Exception as exc:
            raise RuntimeError(
                f"TTS provider returned 200 but body is not JSON: {resp.text[:200]!r}"
            ) from exc
        if not isinstance(peek, dict):
            raise RuntimeError(
                f"TTS provider returned 200 but top-level is {type(peek).__name__}, "
                f"not object: {resp.text[:200]!r}"
            )
        data = peek.get("data")
        audio_hex = (data or {}).get("audio") if isinstance(data, dict) else None
        if isinstance(audio_hex, str) and audio_hex:
            return bytes.fromhex(audio_hex)
        # Persist the full response before we throw — the operator
        # opens the dump file to see what MiniMax actually returned,
        # which is the only way to diagnose region/key/model mismatches.
        _dump_raw_response("minimax", "no_data_audio", resp, resp.text)
        preview = resp.text[:400]
        raise RuntimeError(
            f"TTS response missing data.audio: status={resp.status_code} "
            f"keys={list(peek.keys())!r} body_preview={preview!r}"
        )

    @staticmethod
    def _parse_response(resp: httpx.Response) -> MiniMaxTTSResponse:
        """Validate the JSON envelope and pull out the audio payload.

        Schema reminder (v2):
            {
              "data": {
                "audio": "<hex-encoded mp3 bytes>",
                "status": 1,
                "ced": ""
              },
              "extra_info": {...}
            }
        """
        try:
            payload = resp.json()
        except Exception as exc:
            raise RuntimeError("TTS response was not JSON") from exc
        data = payload.get("data") or {}
        audio_hex = data.get("audio") or ""
        if not audio_hex:
            raise RuntimeError("TTS response missing data.audio")
        # ``status`` is 0 on soft-failures (rate-limit / quota). We
        # treat any non-2xx envelope as a fail regardless; this branch
        # catches the case where MiniMax returns 200 with an empty
        # body (rare but seen during provider-side rebalancing).
        status = data.get("status")
        if status not in (None, 1, 0, 2):
            raise RuntimeError(f"TTS soft-error: status={status}")
        return MiniMaxTTSResponse(
            audio_hex=audio_hex,
            audio_format=str(data.get("audio_format", "mp3")),
        )


# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------


#: Minimal valid MP3 frame header so the bytes pass a quick sniff in the
#: browser (real file detection requires ~3 frames; this is a 1-frame
#: stub that's fine for ``<audio>`` element playback in the catalog
#: demo and Pytest). The point isn't to sound pretty — it's to verify
#: the **wire**, not the audio.
_MOCK_MP3_HEADER = b"\x49\x44\x33"  # "ID3" tag — players treat as metadata-only MP3
_MOCK_MP3_SUFFIX = b"\xff\xfb"  # MPEG audio frame sync — enough for some players to start


def _dump_raw_response(provider: str, reason: str, resp: httpx.Response, body: str) -> None:
    """Persist the full MiniMax response body to disk for postmortem.

    Triggered every time the provider call ends up in an error path.
    Writes under ``$ROLEPLAY_DATA_DIR/logs/tts_<ts>_<reason>.json`` so
    the operator can ``cat`` the file regardless of the truncation
    applied to the error message returned to the SPA.

    The dump is best-effort: a write failure here is *not* a reason
    to mask the upstream error — we only log it to ``logger``
    (which is the project logger, not user-facing).
    """
    from app.infrastructure.config import Settings  # local import keeps top-level cheap

    settings = Settings.from_env()
    out_dir = settings.data_dir / "logs"
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("tts dump: cannot create %s (%s)", out_dir, exc)
        return
    fname = f"tts_{int(time.time() * 1000)}_{provider}_{reason}.json"
    target = out_dir / fname
    try:
        payload = {
            "ts": int(time.time()),
            "provider": provider,
            "reason": reason,
            "request": {
                "method": "POST",
                "url": str(resp.request.url) if resp.request else None,
                "headers_redacted": {k: v for k, v in (resp.request.headers.items() if resp.request else []) if k.lower() != "authorization"},
            },
            "response": {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": body,
            },
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        # Surface the path so the operator sees it in the message they
        # paste into a bug report — the actual content lives in the file.
        body_log = body
        if len(body_log) > 8000:
            body_log = body_log[:8000] + f"... <{len(body) - 8000} more chars>"
        logger.warning("tts dump persisted at %s\nbody preview:\n%s", target, body_log)
    except Exception as exc:  # pragma: no cover — defensive
        logger.debug("tts dump: cannot write %s (%s)", target, exc)


class MockTTSProvider:
    """Deterministic in-process TTS simulator.

    Returns a tiny stub MP3 whose length grows with the requested
    text length so callers can sanity-check that the cache bypassed
    on a hit (no extra bytes leak). Public for tests / catalog demos.
    """

    # Sentinel provider name the route can surface in ``provider`` for
    # debug.
    NAME = "mock/tts-v1"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings

    async def startup(self) -> None:
        """Idempotent no-op — included for parity with MiniMaxTTSProvider."""
        return None

    async def close(self) -> None:
        """Idempotent no-op — no httpx client to close."""
        return None

    @property
    def name(self) -> str:
        """Public identifier surfaced by the route (debug endpoint)."""
        return self.NAME

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        model: str,
        *,
        speed: float = 1.0,
    ) -> bytes:
        """Return a deterministic stub audio blob.

        Composition: ``ID3`` header + scale(text length, capped at 1 KB)
        + frame-sync byte pair. This is enough for ``<audio>`` elements
        to render a (silent) duration and for tests to assert on byte
        length.
        """
        await asyncio.sleep(0)  # cooperative yield; no real latency in tests
        body = text.encode("utf-8")[:512]  # cap so a long message doesn't bloat tests
        return _MOCK_MP3_HEADER + body + _MOCK_MP3_SUFFIX
