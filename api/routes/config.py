"""Configuration routes — read and update runtime settings."""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter, HTTPException

from api.constants import LANGUAGES
from api.schemas import UpdateConfigRequest
from app.application.exceptions import ConfigurationError
from app.bootstrap import reset_container
from app.infrastructure.config import Settings
from app.infrastructure.vectorstore import ChromaKnowledgeBase

router = APIRouter()


@router.get("")
async def get_config():
    """Return current runtime configuration."""
    settings = Settings.from_env()
    # Raw env values so the Settings page can show the user which
    # environment they're running in. ``debug_enabled`` is also
    # surfaced so the System section can flag dev-mode explicitly.
    environment = os.getenv("ENVIRONMENT", "production")
    debug_env = os.getenv("DEBUG", "")
    return {
        "llm_base_url": settings.llm_base_url,
        "chat_model": settings.chat_model,
        "fast_model": settings.fast_model,
        "embedding_model": settings.embedding_model,
        "embedding_base_url": settings.effective_embedding_base_url,  # M13: with LLM fallback
        "embedding_api_key_configured": settings.embedding_api_key
        is not None,  # NEW (bool, no key leak)
        "default_temperature": settings.default_temperature,
        "default_max_tokens": settings.default_max_tokens,
        "db_path": settings.db_path,
        "chroma_persist_dir": settings.chroma_persist_dir,
        "history_limit": settings.history_limit,
        "language": getattr(settings, "language", "en"),
        "theme": getattr(settings, "theme", "system"),
        "knowledge_relevance_threshold": settings.knowledge_relevance_threshold,
        "api_key_configured": settings.llm_api_key is not None,
        "summarize_enabled": settings.summarize_enabled,
        "summarize_max_tokens": settings.summarize_max_tokens,
        "summarize_min_length": settings.summarize_min_length,
        "thread_summary_enabled": settings.thread_summary_enabled,
        "thread_summary_interval": settings.thread_summary_interval,
        "context_compression_enabled": settings.context_compression_enabled,
        "context_compression_threshold": settings.context_compression_threshold,
        "context_compression_keep_recent": settings.context_compression_keep_recent,
        "version": settings.version,
        "environment": environment,
        "debug_enabled": settings.debug_enabled,
        "debug_env_raw": debug_env,
        # ── TTS (text-to-speech) ─────────────────────────────────
        # Surfaced read-only here; the Settings page has a tab that
        # PUTs these back through ``POST /api/config``. ``api_key``
        # flag matches the LLM/embedding pattern so the page can
        # show a "configured" badge without leaking the key.
        "tts_provider": settings.tts_provider,
        "tts_api_key_configured": settings.effective_tts_api_key is not None,
        "tts_base_url": settings.tts_base_url,
        "tts_voice_id": settings.tts_voice_id,
        "tts_model": settings.tts_model,
        "tts_speed": settings.tts_speed,
        "tts_cache_dir": settings.tts_cache_dir,
    }


@router.get("/languages")
async def list_languages():
    return LANGUAGES


@router.post("")
async def update_config(body: UpdateConfigRequest):
    """Update runtime configuration in .env."""

    # .env is always relative to project root
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)

    # Apply updates using dotenv helpers
    env_updates = {
        "DEFAULT_TEMPERATURE": f"{body.temperature:.1f}" if body.temperature is not None else None,
        "DEFAULT_MAX_TOKENS": str(body.max_tokens) if body.max_tokens is not None else None,
        "FAST_MODEL": body.fast_model,
        "EMBEDDING_MODEL": body.embedding_model,
        "EMBEDDING_BASE_URL": body.embedding_base_url,  # NEW
        "EMBEDDING_API_KEY": body.embedding_api_key,  # NEW; None = don't change, "" = clear
        "KNOWLEDGE_RELEVANCE_THRESHOLD": str(body.knowledge_relevance_threshold)
        if body.knowledge_relevance_threshold is not None
        else None,
        "APP_LANGUAGE": body.language,
        "APP_THEME": body.theme,
        "SUMMARIZE_ENABLED": str(body.summarize_enabled).lower()
        if body.summarize_enabled is not None
        else None,
        "SUMMARIZE_MAX_TOKENS": str(body.summarize_max_tokens)
        if body.summarize_max_tokens is not None
        else None,
        "SUMMARIZE_MIN_LENGTH": str(body.summarize_min_length)
        if body.summarize_min_length is not None
        else None,
        "THREAD_SUMMARY_ENABLED": str(body.thread_summary_enabled).lower()
        if body.thread_summary_enabled is not None
        else None,
        "THREAD_SUMMARY_INTERVAL": str(body.thread_summary_interval)
        if body.thread_summary_interval is not None
        else None,
        "CONTEXT_COMPRESSION_ENABLED": str(body.context_compression_enabled).lower()
        if body.context_compression_enabled is not None
        else None,
        "CONTEXT_COMPRESSION_THRESHOLD": str(body.context_compression_threshold)
        if body.context_compression_threshold is not None
        else None,
        "CONTEXT_COMPRESSION_KEEP_RECENT": str(body.context_compression_keep_recent)
        if body.context_compression_keep_recent is not None
        else None,
        "HISTORY_LIMIT": str(body.history_limit) if body.history_limit is not None else None,
        # ── TTS (text-to-speech) ─────────────────────────────────
        # Persisted via the same dotenv set_key + reset_container
        # dance as the rest of the schema. ``tts_api_key`` writes
        # an empty string as "" which Settings reads as ``None``
        # ("use llm_api_key fallback") — see ``Settings.preprocess``.
        "TTS_PROVIDER": body.tts_provider,
        "TTS_API_KEY": body.tts_api_key,
        "TTS_BASE_URL": body.tts_base_url,
        "TTS_VOICE_ID": body.tts_voice_id,
        "TTS_MODEL": body.tts_model,
        "TTS_SPEED": str(body.tts_speed) if body.tts_speed is not None else None,
        "TTS_CACHE_DIR": body.tts_cache_dir,
    }

    for env_key, value in env_updates.items():
        if value is not None:
            set_key(str(env_path), env_key, value)

    # Apply to current process
    for env_key, value in env_updates.items():
        if value is not None:
            os.environ[env_key] = value

    reset_container()

    # Re-read and return updated config
    # TODO(for-assistant): протестировать получше, замечал поломку работы бекенда после сохранения настроек, отправка сообщений в чат возвращает ошибку
    return await get_config()


@router.post("/reindex")
async def reindex_knowledge_base():
    """Wipe all Chroma collections and reindex from scratch.

    Call this after changing the embedding model to regenerate
    all vector embeddings. Safe to call even when embeddings
    are disabled (no-op).
    """
    kb = ChromaKnowledgeBase()
    stats = kb.reindex_all()
    return {
        "ok": True,
        "detail": f"Removed {stats['collections_removed']} collection(s). "
        "Knowledge base will be rebuilt on next interaction.",
    }


@router.get("/knowledge/status")
async def knowledge_status():
    """Return stale bot IDs and current embedding configuration."""
    from app.bootstrap import get_container
    from app.infrastructure.config import Settings
    from app.infrastructure.vectorstore import ChromaKnowledgeBase

    settings = Settings.from_env()
    kb = ChromaKnowledgeBase(settings=settings)
    stale = kb.scan_for_stale_collections()
    container = get_container()
    return {
        "stale_bot_ids": stale,
        "embedding_model": settings.embedding_model,
        "embedding_base_url": settings.effective_embedding_base_url,  # M13
        "reindex_in_progress": container.reindex.is_running,
        "reindex_job_id": container.reindex.running_job_id,
    }


@router.post("/knowledge/reindex")
async def reindex_all_knowledge():
    """Start reindex for all stale bots. Returns job_id or 409 if already running."""
    from app.bootstrap import get_container
    from app.infrastructure.config import Settings
    from app.infrastructure.vectorstore import ChromaKnowledgeBase

    container = get_container()
    if container.reindex.is_running:
        raise HTTPException(
            status_code=409,
            detail=f"Reindex already running: {container.reindex.running_job_id}",
        )

    settings = Settings.from_env()
    kb = ChromaKnowledgeBase(settings=settings)
    stale = kb.scan_for_stale_collections()
    if not stale:
        return {"ok": True, "job_id": None, "stale_bots": []}

    job = await container.reindex.start(kb, stale)
    return {"ok": True, "job_id": job.job_id, "stale_bots": stale}


@router.post("/knowledge/reindex/{job_id}/cancel")
async def cancel_reindex(job_id: str):
    """Cancel an in-flight reindex job. Returns 404 if job is unknown."""
    from app.bootstrap import get_container

    container = get_container()
    job = container.reindex.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    cancelled = container.reindex.cancel(job_id)
    return {"ok": True, "cancel_requested": cancelled}


@router.get("/knowledge/reindex/{job_id}/stream")
async def reindex_stream(job_id: str):
    """SSE stream of progress events for a reindex job."""
    from fastapi.responses import StreamingResponse

    from app.bootstrap import get_container

    container = get_container()

    async def event_stream() -> AsyncIterator[bytes]:
        while True:
            job = container.reindex.get(job_id)
            if job is None:
                yield f"event: error\ndata: {json.dumps({'detail': 'job not found'})}\n\n".encode()
                return
            yield f"event: progress\ndata: {json.dumps(job.to_dict())}\n\n".encode()
            if job.status in ("completed", "failed", "cancelled"):
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/validate-embedding")
async def validate_embedding_endpoint_route(body: UpdateConfigRequest):
    """Test that the embedding endpoint is reachable and accepts a test request.

    Used by the wizard and Settings page to validate before saving.
    """
    from app.infrastructure.embedding_validation import validate_embedding_endpoint

    if not body.embedding_model:
        raise HTTPException(status_code=400, detail="embedding_model is required")
    if not body.embedding_base_url:
        raise HTTPException(status_code=400, detail="embedding_base_url is required")

    try:
        validate_embedding_endpoint(
            body.embedding_base_url, body.embedding_api_key, body.embedding_model
        )
    except ConfigurationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}
