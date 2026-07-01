"""Chat routes — send message + SSE streaming + branching support."""

import asyncio
import io
import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, status
from starlette.requests import Request
from starlette.responses import StreamingResponse

from api.deps import ContainerDep
from api.schemas import ChatRequest, RegenerateRequest
from app.application.dto import AbortResult, SendMessageCommand
from app.application.exceptions import NotFoundError

logger = logging.getLogger(__name__)

router = APIRouter()


def _format_chat_chunk_event(item: Any) -> str:
    """Render a single stream chunk as one or more ``data: ...\\n\\n`` SSE lines.

    Accepts both ``ChatChunk`` (the application-layer DTO used by the
    production ``ChatService.stream_message`` path) and the lower-level
    ``LLMChunk`` dataclass (yielded by ``MockChatService.start_stream``
    and the SSE stream task in tests). Both expose the same three core
    channels — ``content``, ``reasoning``, ``usage`` — and the
    ``debug`` channel is only populated on ``ChatChunk`` (production
    wires ``ChatChunk.debug`` through the orchestrator's debug-messages
    side channel; test doubles never do). Chunks that are empty on
    every channel contribute no events at all.

    The ``debug`` channel is gated by ``Settings.debug_enabled`` at the
    service layer — when debug is off, ``ChatChunk.debug`` is always
    ``None`` and this function never emits a ``debug`` event. In
    production the field is never populated, so the wire stays clean.

    Exposed at module scope for unit testing — the production SSE
    generator just calls this in a loop.
    """
    events: list[dict[str, Any]] = []
    if getattr(item, "reasoning", None):
        events.append({"type": "reasoning", "content": item.reasoning})
    if getattr(item, "content", None):
        events.append({"type": "chunk", "content": item.content})
    usage = getattr(item, "usage", None)
    if usage is not None:
        events.append({"type": "usage", "usage": usage})
    # The dev-mode debug payload is only ever populated on ChatChunk
    # (LLMChunk has ``debug_messages`` instead — the service translates
    # that into ``ChatChunk.debug``). We check for the attribute
    # defensively so this function works for both shapes.
    debug = getattr(item, "debug", None)
    if debug is not None and hasattr(debug, "model_dump"):
        events.append({"type": "debug", "debug": debug.model_dump()})
    return "".join(f"data: {json.dumps(ev)}\n\n" for ev in events)


@router.post("/{thread_id}/messages")
async def send_message(
    thread_id: int,
    body: ChatRequest,
    container: ContainerDep,
    request: Request,
):
    """Send a message and stream the response via SSE."""
    if container.chat is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured. Please set up an API key first.",
        )

    command = SendMessageCommand(
        thread_id=thread_id,
        bot_id=body.bot_id,
        user_input=body.user_input,
        persona_id=body.persona_id,
        file_ids=body.file_ids or [],
    )

    # Schedule background summarization as a *detached* task so the
    # HTTP response returns as soon as the SSE stream finishes — not
    # after LLM calls for short_content generation. We previously
    # used ``BackgroundTasks.add_task`` which blocks the response
    # for the full duration of ``run_summarization`` (~6s for a
    # 7-message batch on DeepSeek), making the chat UI appear stuck
    # on "loading" even though the LLM already finished.
    #
    # Two safeguards: the task is stored on ``container`` so the GC
    # doesn't drop it before completion, and any exception inside
    # the task is logged but never propagates (fire-and-forget).
    if container.summarizer is not None:
        task = asyncio.create_task(
            container.chat.run_summarization(thread_id),
            name=f"summarize-{thread_id}",
        )
        # Keep a strong reference so the task isn't garbage-collected
        # mid-flight. ``ApplicationContainer`` is frozen, so we
        # attach via a private dict instead.
        _background_tasks = getattr(container, "_bg_tasks", None)
        if not isinstance(_background_tasks, set):
            _background_tasks = set()
            try:
                object.__setattr__(container, "_bg_tasks", _background_tasks)
            except (AttributeError, TypeError):
                # If we can't attach, fall back to keeping a local
                # reference so the task is still alive long enough
                # to run.
                _background_tasks = set()
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

        def _log_exception(t: asyncio.Task) -> None:
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                logger.exception(
                    "Background summarization failed for thread %d: %s",
                    thread_id,
                    exc,
                )

        task.add_done_callback(_log_exception)

    # Spawn the LLM stream in a registered Task so /api/threads/{id}/abort
    # can cancel it. The route's job is just to drain the queue into SSE.
    _stream_task, chunk_queue = container.chat.start_stream(command)

    async def event_stream():
        try:
            yield f"data: {json.dumps({'type': 'meta', 'thread_id': thread_id})}\n\n"

            while True:
                # Bail out early if the client disconnected.
                if await request.is_disconnected():
                    _stream_task.cancel()
                    break

                # Wait for the next chunk (None = end of stream, exc = error).
                item = await chunk_queue.get()
                if item is None:
                    break
                if isinstance(item, BaseException):
                    yield f"data: {json.dumps({'type': 'error', 'detail': str(item)})}\n\n"
                    break
                # Reasoning (chain-of-thought), content, and dev-mode
                # token usage are forwarded as independent SSE events so
                # the frontend can render each channel without coupling.
                # Reasoning never reaches the persisted message — only
                # the visible content is stored in the DB. Usage is
                # skipped when the provider doesn't emit it.
                yield _format_chat_chunk_event(item)

            if not await request.is_disconnected():
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except NotFoundError as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        finally:
            # M-review2: guarantee the LLM task is cancelled even on
            # unexpected exceptions or ASGI-driven generator close,
            # so the producer doesn't keep writing into chunk_queue
            # after the consumer is gone.
            if not _stream_task.done():
                _stream_task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{thread_id}/messages/{message_id}/regenerate")
async def regenerate_message(
    thread_id: int,
    message_id: int,
    body: RegenerateRequest,
    container: ContainerDep,
    request: Request,
):
    """Regenerate a bot message by branching — deletes subsequent messages,
    creates a new branch version, and streams the new response via SSE."""
    if container.chat is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured. Please set up an API key first.",
        )

    _stream_task, event_queue = container.chat.start_regenerate(
        thread_id, message_id, body.bot_id, body.persona_id
    )

    async def event_stream():
        try:
            while True:
                if await request.is_disconnected():
                    _stream_task.cancel()
                    break

                item = await event_queue.get()
                if item is None:
                    break
                if isinstance(item, BaseException):
                    yield f"data: {json.dumps({'type': 'error', 'detail': str(item)})}\n\n"
                    break
                yield f"data: {json.dumps(item)}\n\n"
        except NotFoundError as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        finally:
            # M-review2: pair with the early-disconnect cancel above
            # so the producer never outlives the SSE consumer.
            if not _stream_task.done():
                _stream_task.cancel()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/{thread_id}/messages/{message_id}/retry")
async def retry_message(
    thread_id: int,
    message_id: int,
    body: RegenerateRequest,
    container: ContainerDep,
    request: Request,
):
    """Retry from a user message — delete everything after it and generate a fresh response.

    Unlike regenerate (which branches an assistant message), this re-uses the
    existing user message without creating a duplicate in the database.
    """
    if container.chat is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured. Please set up an API key first.",
        )

    async def event_stream():
        try:
            async for event in container.chat.retry_message(
                thread_id, message_id, body.bot_id, body.persona_id
            ):
                if await request.is_disconnected():
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except NotFoundError as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{thread_id}/messages/{message_id}/versions")
async def get_message_versions(
    thread_id: int,
    message_id: int,
    container: ContainerDep,
):
    """Get all versions of a branched message."""
    try:
        versions = await container.threads.get_versions(message_id)
        return {"versions": [v.model_dump() for v in versions]}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{thread_id}/messages/{message_id}/switch/{target_version_id}")
async def switch_message_version(
    thread_id: int,
    message_id: int,
    target_version_id: int,
    container: ContainerDep,
):
    """Switch to a different version of a branched message."""
    try:
        await container.threads.switch_version(thread_id, message_id, target_version_id)
        # Get the newly active message
        messages = await container.threads.list_messages(thread_id)
        active = next((m for m in messages if m.id == target_version_id), None)
        return {"success": True, "message": active.model_dump() if active else None}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{thread_id}/export")
async def export_chat(thread_id: int, container: ContainerDep):
    """Export the entire thread conversation as a JSON file."""
    try:
        messages = await container.threads.export_messages(thread_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    json_bytes = json.dumps(
        [m.model_dump(mode="json") for m in messages],
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")

    return StreamingResponse(
        io.BytesIO(json_bytes),
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="thread-{thread_id}-export.json"',
        },
    )


@router.post("/{thread_id}/abort", response_model=AbortResult)
async def abort_generation(
    thread_id: int,
    container: ContainerDep,
) -> AbortResult:
    """Cancel an in-flight LLM stream for this thread.

    Idempotent — returns ``was_active=false`` if no stream is running.
    """
    return await container.chat.abort_generation(thread_id)
