"""Thread CRUD routes."""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from api.deps import ContainerDep
from api.schemas import EditMessageRequest
from app.application.dto import MessageDTO, RecentThreadDTO, ThreadDTO, ThreadStatsDTO
from app.application.exceptions import NotFoundError

router = APIRouter()


# ── Set first message (greeting choice) ──────────────────────────────


class SetFirstMessageRequest(BaseModel):
    greeting_index: int


class ForkThreadRequest(BaseModel):
    """Body of ``POST /api/threads/{thread_id}/fork``.

    ``message_id`` is the id of the message the user clicked the fork
    icon on. The backend snapshots the active conversation up to and
    including this message into a new thread and returns the new
    thread id so the frontend can redirect.
    """

    message_id: int = Field(gt=0)


@router.put("/{thread_id}/first-message")
async def set_first_message(
    thread_id: int,
    body: SetFirstMessageRequest,
    container: ContainerDep,
):
    """Overwrite the first assistant message of a thread with the chosen greeting.

    ``greeting_index`` is the position in ``[bot.first_message, *bot.alternate_greetings]``
    (0 → first_message, 1+ → alternate_greetings[index-1]).
    """
    try:
        thread = await container.threads.get_thread(thread_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    try:
        await container.threads.set_first_message(thread_id, thread.bot_id, body.greeting_index)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return {"ok": True}


# ── Recent threads (MUST be before /{thread_id} routes) ──────────────


@router.get("/recent", response_model=list[RecentThreadDTO])
async def list_recent_threads(container: ContainerDep, limit: int = 20, bot_id: int | None = None):
    """Get recent threads with bot info, persona name, and last message preview."""
    return await container.threads.list_recent_threads(limit, bot_id=bot_id)


# ── Thread CRUD ──────────────────────────────────────────────────────


@router.get("/{thread_id}", response_model=ThreadDTO)
async def get_thread(thread_id: int, container: ContainerDep):
    try:
        return await container.threads.get_thread(thread_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{thread_id}")
async def rename_thread(thread_id: int, name: str, container: ContainerDep):
    try:
        await container.threads.rename_thread(thread_id, name)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{thread_id}")
async def delete_thread(thread_id: int, container: ContainerDep):
    try:
        await container.threads.delete_thread(thread_id)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{thread_id}/persona")
async def set_thread_persona(
    thread_id: int, container: ContainerDep, persona_id: int | None = None
):
    """Set the active persona for a thread. Pass persona_id=0 or omit to clear."""
    try:
        pid = persona_id if persona_id and persona_id > 0 else None
        await container.threads.set_thread_persona(thread_id, pid)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{thread_id}/clear")
async def clear_thread(thread_id: int, container: ContainerDep):
    try:
        await container.threads.clear_conversation(thread_id)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get("/{thread_id}/messages", response_model=list[MessageDTO])
async def list_messages(
    thread_id: int,
    container: ContainerDep,
    limit: int | None = None,
    before_id: int | None = None,
):
    from app.infrastructure.config import Settings

    if limit is None:
        limit = Settings.from_env().history_limit
    return await container.threads.list_messages(thread_id, limit, before_id=before_id)


@router.get("/{thread_id}/stats", response_model=ThreadStatsDTO)
async def get_thread_stats(thread_id: int, container: ContainerDep):
    """Header-level stats (real message total + token estimate).

    Complements the paginated ``GET /threads/{id}/messages`` so the
    chat header can render the true size of the thread instead of just
    the latest 50-message window. The token estimate mirrors the
    frontend's chars/4 proxy so the two stay in lockstep.
    """
    try:
        return await container.threads.get_stats(thread_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{thread_id}/messages/{message_id}")
async def update_message(
    thread_id: int,
    message_id: int,
    body: EditMessageRequest,
    container: ContainerDep,
):
    try:
        new_id = await container.threads.update_message(
            thread_id, message_id, body.content, state=body.state
        )
        return {"ok": True, "message_id": new_id}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{thread_id}/messages/last")
async def delete_last_message(thread_id: int, container: ContainerDep):
    messages = await container.threads.list_messages(thread_id, limit=1)
    if not messages:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No messages to delete")
    last_id = messages[-1].id
    if last_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message has no id")
    await container.threads.delete_message(last_id)
    return {"ok": True}


@router.delete("/{thread_id}/messages/{message_id}")
async def delete_message(thread_id: int, message_id: int, container: ContainerDep):
    """Delete a single message."""
    try:
        await container.threads.delete_message(message_id)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{thread_id}/messages/{message_id}/cascade")
async def cascade_delete_messages(thread_id: int, message_id: int, container: ContainerDep):
    """Delete a message and all messages after it."""
    try:
        await container.threads.delete_message_cascade(thread_id, message_id)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{thread_id}/fork", response_model=ThreadDTO)
async def fork_thread(
    thread_id: int,
    body: ForkThreadRequest,
    container: ContainerDep,
):
    """Snapshot the conversation up to ``message_id`` into a new thread.

    The user-facing contract: the user clicks a fork icon on a
    message in the chat UI, this endpoint produces an independent
    thread containing a copy of every active message up to and
    including that message, and the frontend redirects them to the
    new thread.

    Returns the new thread's ``ThreadDTO`` so the client can wire it
    straight into the chat header without a follow-up GET.

    Errors:

    * ``404 NotFoundError`` — source thread doesn't exist, or the
      supplied ``message_id`` doesn't belong to the source thread
      (idempotent on the not-found contract so the frontend can
      fall back to a friendly error toast).
    """
    try:
        new_thread_id = await container.threads.fork_at_message(
            thread_id=thread_id, message_id=body.message_id
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    # ``fork_at_message`` returns the new id, but we always re-fetch
    # the DTO so the response shape (with name, summary, persona_id
    # populated by the repo) matches every other endpoint that
    # returns ``ThreadDTO``.
    return await container.threads.get_thread(new_thread_id)


# ── Context Compression ──────────────────────────────────────────────


@router.post("/{thread_id}/summarize")
async def summarize_thread(thread_id: int, container: ContainerDep):
    """Generate a thread-level summary from recent messages."""
    if container.summarizer is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured. Please set up an API key first.",
        )

    from app.infrastructure.config import Settings

    limit = Settings.from_env().history_limit
    messages = await container.threads.list_messages(thread_id, limit=limit)
    if not messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No messages to summarize"
        )

    summary = await container.summarizer.summarize_thread_recent(
        thread_id,
        messages,
    )
    if not summary:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate summary. The LLM returned an empty response.",
        )
    # Persist the summary so it shows up in recent-chats preview. The
    # background ``run_summarization`` task does this on its own
    # interval, but the manual button was generating a summary in
    # memory and then throwing it away — the response showed the text
    # but ``chat_threads.summary`` stayed NULL.
    await container.threads.update_thread_summary(thread_id, summary)
    return {"ok": True, "summary": summary}
