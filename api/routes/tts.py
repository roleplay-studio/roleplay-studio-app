"""HTTP endpoints for text-to-speech.

Wire shape
----------
* ``POST /api/tts/synthesize`` — body is the text to speak. Returns
  ``{"cache_id": "<16 hex chars>", "from_cache": bool, "audio_url": "<...>"}``.
  The client then plays ``audio_url`` straight from disk via a normal
  ``<audio>`` element; we never stream MP3 from this endpoint because
  the GET endpoint is cheaper (and the frontend can preload it).

* ``GET /api/tts/audio/{cache_id}`` — streams the cached MP3 bytes
  with ``Content-Type: audio/mpeg``. 404 if the id is unknown
  (e.g. server lost its cache directory) or the TTS provider is
  disabled.

Provider opt-in
---------------
Both endpoints return ``503`` when ``Settings.tts_provider ==
"disabled"``. The frontend uses this signal to hide the play button
entirely so users running with TTS disabled don't see a dead UI.

Caching / invalidation
----------------------
The cache is on disk under ``Settings.tts_cache_dir``. Operators
can clear it manually (delete the folder); nothing in the app
references the bytes by content outside of this module. There's no
HTTP-level TTL because the audio is content-addressed — cache invalidation
just means deleting the file.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from api.deps import ContainerDep
from app.application.services.tts import TTSError

router = APIRouter()


class SynthesizeRequest(BaseModel):
    """Body for ``POST /api/tts/synthesize``.

    All fields except ``text`` are optional so the frontend can hit
    this with just the message body and inherit the server-side
    defaults from ``Settings.tts_*``. ``voice_id`` and ``model``
    override per-message; ``speed`` is a 0.5..2.0 multiplier.
    """

    text: str = Field(min_length=1, max_length=4000)
    voice_id: str | None = None
    model: str | None = None
    speed: float = Field(default=1.0, ge=0.5, le=2.0)


class SynthesizeResponse(BaseModel):
    """Body for the 200 response.

    ``audio_url`` is the path the client should fetch via ``<audio>``
    (relative to the API origin). ``cache_id`` is also returned so
    the client can show the action on retry / cache-hit telemetry.
    """

    cache_id: str
    audio_url: str
    from_cache: bool


def _tts_disabled() -> None:
    """Single source of the disabled-provider 503 message."""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="TTS is disabled on this server. Set TTS_PROVIDER in .env.",
    )


@router.post(
    "/synthesize",
    response_model=SynthesizeResponse,
    summary="Synthesize (or fetch from cache) the text-to-speech for a message",
)
async def synthesize(req: SynthesizeRequest, container: ContainerDep) -> SynthesizeResponse:
    """Synthesize ``req.text`` and return the cache id + audio URL.

    Implementation: the route lives in ``api/`` and the cache lives
    in the application layer (``TTSService.synthesize``); we don't
    store anything in our own DB because the audio file already
    names itself (cache_id = sha256(model|voice|text)[:16]).
    """
    if container.tts is None:
        _tts_disabled()
    try:
        result = await container.tts.synthesize(  # type: ignore[union-attr] — _tts_disabled raised
            req.text,
            voice_id=req.voice_id,
            model=req.model,
            speed=req.speed,
        )
    except TTSError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"TTS provider error: {exc}",
        ) from exc
    return SynthesizeResponse(
        cache_id=result.cache_id,
        audio_url=f"/api/tts/audio/{result.cache_id}",
        from_cache=result.from_cache,
    )


@router.get(
    "/audio/{cache_id}",
    summary="Stream a previously synthesised audio by cache id",
    responses={
        200: {"content": {"audio/mpeg": {}}},
        404: {"description": "Unknown cache id — re-synthesize first"},
        503: {"description": "TTS is disabled on this server"},
    },
)
async def get_audio(cache_id: str, container: ContainerDep) -> Response:
    """Return the cached MP3 bytes for ``cache_id``.

    ``cache_id`` is 16 hex chars (sha256 prefix). Anything that
    doesn't match is rejected with 400 — otherwise a typo'd id would
    look like a cache miss and masquerade as a 404.
    """
    if not cache_id.isalnum() or len(cache_id) != 16:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="cache_id must be 16 hex chars",
        )
    if container.tts is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS is disabled on this server",
        )
    try:
        audio = container.tts.load_cached(cache_id)
    except TTSError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    # ``Content-Disposition: inline`` so the browser plays it through
    # ``<audio>`` rather than downloading. filename is just a hint for
    # users who hit "save audio as".
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Content-Disposition": f'inline; filename="tts_{cache_id}.mp3"'},
    )
