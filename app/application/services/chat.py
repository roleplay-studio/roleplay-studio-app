"""Chat service — orchestrates conversation generation with context, memory, persona, and branching support."""

import asyncio
import logging
import uuid as uuid_lib
from collections.abc import AsyncGenerator

from app.application.dto import (
    AbortResult,
    ChatChunk,
    ChatResponse,
    ConversationRequest,
    LLMDebugInfo,
    MessageDTO,
    SendMessageCommand,
)
from app.application.exceptions import ExternalServiceError, NotFoundError
from app.application.ports import (
    BotRepository,
    ConversationOrchestratorPort,
    KnowledgeBaseRepository,
    LLMPort,
    MarkdownRepairer,
    MessageRepository,
    PersonaRepository,
    ThreadFileRepository,
    ThreadRepository,
)
from app.application.services.message_summarizer import MessageSummarizer
from app.domain.enums import BotType
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)


class _NullMarkdownRepairer:
    """No-op fallback so ChatService can be constructed in tests
    without wiring a real repairer.

    Implements the ``MarkdownRepairer`` Protocol structurally (the
    ``repair`` method has the right signature). Returning ``text``
    unchanged is correct for tests that don't exercise the
    markdown-repair code path.
    """

    def repair(self, text: str, mode: str = "close") -> str:
        return text


def _repair_for_rp(
    repairer: MarkdownRepairer,
    bot_type: BotType | str | None,
    text: str,
) -> str:
    """Run ``repairer.repair(text)`` only if ``bot_type`` is RP.

    Assistant/Agent bots speak in plain prose (no markdown
    emphasis), so repairing their output is a no-op. The function
    returns ``text`` unchanged when ``bot_type`` is anything other
    than ``BotType.RP`` (and tolerates string values like ``"rp"``
    coming through ``SendMessageCommand`` before the
    ``BotType`` enum is applied).

    ``bot_type`` may be ``None`` (e.g. a legacy command that did
    not pass it) — we treat ``None`` as "unknown" and skip the
    repair rather than guessing. This matches the conservative
    behaviour of other bot_type branches in the service
    (``bot.bot_type or BotType.RP`` resolves it eagerly there).

    ``text`` must be non-empty — callers gate the call on
    ``if response:`` already (and an empty string is a no-op for
    the repairer anyway).
    """
    if text == "":
        return text
    # Normalise string <-> enum. BotType.value is "rp"/"assistant"/"agent".
    if isinstance(bot_type, str):
        normalised = bot_type.lower()
    elif isinstance(bot_type, BotType):
        normalised = bot_type.value.lower()
    else:
        return text
    if normalised != BotType.RP.value:
        return text
    return repairer.repair(text)


class ChatService:
    def __init__(
        self,
        bots: BotRepository,
        messages: MessageRepository,
        knowledge: KnowledgeBaseRepository,
        orchestrator: ConversationOrchestratorPort,
        settings: Settings | None = None,
        personas: PersonaRepository | None = None,
        threads: ThreadRepository | None = None,
        llm: LLMPort | None = None,
        fast_llm: LLMPort | None = None,
        files: ThreadFileRepository | None = None,
        summarizer: MessageSummarizer | None = None,
        markdown_repairer: MarkdownRepairer | None = None,
    ):
        self._bots = bots
        self._messages = messages
        self._knowledge = knowledge
        self._orchestrator = orchestrator
        # Settings is injected once at construction time. The previous
        # implementation called Settings.from_env() on every request
        # (K3 in docs/review.md) which both wasted work and created an
        # architectural mismatch: the orchestrator caches settings,
        # the service re-reads them — the two could disagree.
        # Default to Settings.from_env() to keep tests/back-compat
        # working — bootstrap.py passes an explicit instance in prod.
        self._settings: Settings = settings or Settings.from_env()
        self._personas = personas
        self._threads = threads
        # ``self._llm`` is the chat-quality model — used for the
        # primary chat stream. ``self._fast_llm`` is the cheap model
        # used for background tasks (state regeneration, thread
        # auto-naming). They share the same ``LLMPort`` contract but
        # are wired to different providers in production: chat uses
        # ``chat_model``, background uses ``fast_model``. When only
        # ``llm`` is supplied, state-regen falls back to it (matches
        # the pre-fix behaviour for tests that don't bother wiring
        # two providers).
        self._llm = llm
        self._fast_llm: LLMPort | None = fast_llm
        self._files = files
        self._summarizer = summarizer
        # Default to a no-op repairer so unit tests that construct
        # ChatService without explicit DI don't need the
        # format-standart-rp library installed. Production wiring
        # in app.bootstrap.py always passes a real implementation.
        self._markdown_repairer: MarkdownRepairer = (
            markdown_repairer if markdown_repairer is not None else _NullMarkdownRepairer()
        )
        # NOTE: the old `_first_message_saved: set[int]` in-memory
        # registry was removed (K4 in docs/review.md). It had three
        # problems:
        #   1. lost on process restart → duplicated first_message
        #   2. race condition under two concurrent stream_message
        #   3. useless across multiple uvicorn workers
        # Replacement: stream_save_first_message() now consults the DB
        # via MessageRepository.get_first_assistant() (idempotent under
        # concurrent writes because both paths go through the DB).
        # Registry of in-flight LLM stream tasks, keyed by thread_id.
        # Populated by `register_stream` at the start of stream_message
        # / stream_branch so /api/threads/{id}/abort can cancel them.
        #
        # ── MULTI-WORKER WARNING ─────────────────────────────────────
        # This dict is **per-process** — it does not coordinate across
        # uvicorn workers (or pods in k8s). Under ``uvicorn --workers N``
        # or a k8s Deployment with replicas>1, two workers can each
        # have an active stream for the same ``thread_id`` because the
        # POST /chat endpoint is stateless at the load-balancer level.
        # The frontend will see two parallel SSE streams from the same
        # thread, both with their own task in ``_active_streams``,
        # both calling ``abort_generation`` only cancelling the local
        # worker's task.
        #
        # The fix for multi-worker deployments is **NOT** in this
        # codebase: add a distributed lock (Redis SETNX with TTL, or
        # Postgres advisory lock, or etcd lease) keyed on
        # ``f"chat-stream:{thread_id}"``. The ``start_stream`` path
        # should acquire the lock before ``asyncio.create_task``; if
        # the lock is held by another worker, it should return a
        # 409 Conflict (or stream the in-progress worker's chunks
        # via a pub/sub channel — that's a larger refactor).
        # Tracked as Sprint 4c / Sprint 6+ in docs/review.md.
        self._active_streams: dict[int, asyncio.Task] = {}

    # ── Section 1: History & first-message ─────────────────────────

    async def _load_full_history(self, thread_id: int) -> list[MessageDTO]:
        """Load the full conversation history for ``thread_id``.

        Defaults the page size to ``Settings.history_limit`` (1000) so
        the ``MessageRepository.list_for_thread`` default of ``limit=20``
        — designed for the chat UI's first page — never silently
        truncates the LLM context. DEBUG1 had 91 active messages but
        the LLM was only seeing 20 because every ``list_for_thread``
        call here used to omit the limit argument.

        The compression stage (see ``_compress_history``) still kicks
        in above ``Settings.context_compression_threshold`` to keep
        the LLM prompt within sane token bounds.

        When the loaded page is exactly as long as the cap, the DB may
        still hold older rows that we silently dropped — log a warning
        so a thread that outgrew ``history_limit`` is observable in
        operator logs and the user knows to raise the cap in Settings.
        The previous behaviour (200 default) produced "203 TURNS" in
        the LLM debug panel on a 373-message thread with no signal
        that 170 messages had been dropped on the floor.
        """
        limit = self._settings.history_limit
        messages = await self._messages.list_for_thread(thread_id, limit=limit)
        if len(messages) >= limit:
            logger.warning(
                "Thread %d returned %d messages — at the history_limit cap (%d). "
                "Older messages were not loaded; raise HISTORY_LIMIT in Settings to see them.",
                thread_id,
                len(messages),
                limit,
            )
        return messages

    async def send_message(self, command: SendMessageCommand) -> ChatResponse:
        request = await self._build_request(command)
        response = await self._orchestrator.generate(request)
        await self._messages.save_exchange(command.thread_id, command.user_input, response)
        return ChatResponse(content=response)

    async def stream_save_first_message(self, thread_id: int, bot_id: int) -> None:
        """Save the bot's first_message as the initial message in a thread.

        Idempotency strategy (RC1.2 in docs/review.md): delegate the
        check-then-insert to ``MessageRepository.save_first_assistant_if_absent``
        which executes the ``SELECT COUNT + INSERT`` pair inside a single
        SQLite session. aiosqlite serializes concurrent writers, so two
        racing calls can no longer both pass the existence check.

        Earlier in-memory ``_first_message_saved: set[int]`` (removed in
        Sprint 1 / K4) and the DB-based ``get_first_assistant`` lookup
        (added in Sprint 1) were both racy under aiosqlite; this
        repository-level atomicity closes the gap without adding
        SELECT-then-INSERT window.
        """
        bot = await self._bots.get(bot_id)
        if bot is None or not bot.first_message:
            return
        await self._messages.save_first_assistant_if_absent(thread_id, bot.first_message)

    # ── Section 2: Streaming core (the LLM call path) ──────────────

    async def stream_message(self, command: SendMessageCommand) -> AsyncGenerator[ChatChunk]:
        # 1. Save first_message FIRST if this is a new thread
        # This ensures correct order in DB: first_message → user → assistant
        # (files need user message_id, so we save user after first_message)
        if command.bot_id is not None:
            await self.stream_save_first_message(command.thread_id, command.bot_id)

        # Resolve bot_type up-front so the markdown repair call below
        # (in the CancelledError/Exception handlers and the success
        # path) doesn't have to re-fetch the bot. One PK SELECT per
        # turn; the alternative (passing bot_type through every
        # helper) would force a wider refactor for no real saving.
        bot = await self._bots.get(command.bot_id)
        bot_type: str | None = bot.bot_type if bot is not None else None

        # 2. Save user message — needed for file attachment (we need message_id)
        user_msg_id = await self._messages.save(
            command.thread_id, "user", command.user_input, generation_status="complete"
        )

        # Attach uploaded files to this user message
        if command.file_ids and user_msg_id is not None and self._files is not None:
            try:
                await self._files.attach_to_message(command.file_ids, user_msg_id)
            except asyncio.CancelledError:
                # m7: abort takes priority over file attach. Without
                # this explicit re-raise, the broad ``except
                # Exception:`` below would let the cancellation
                # propagate only as a logged warning, masking the
                # abort signal in the route handler.
                raise
            except Exception:
                # m5: keep the broad catch. File attach is
                # fire-and-forget after the main message is saved;
                # a single failure here shouldn't fail the whole
                # user message. Specific exception types (httpx,
                # sqlalchemy, OSError) are all wrapped under
                # Exception — narrowing further isn't worth the
                # maintenance cost for a non-critical path.
                logger.exception("Failed to attach files to message %d", user_msg_id)

        request = await self._build_request(command)

        content_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        # ``debug_enabled`` gates the dev-mode LLM debug payload end to
        # end — in production the orchestrator still yields the
        # ``debug_messages`` chunk but the service drops it on the floor
        # before it ever reaches the SSE route.
        # Settings are now injected once at construction (K3 fix) — no
        # per-request re-read of the entire .env.
        debug_enabled = self._settings.debug_enabled
        try:
            async for llm_chunk in self._orchestrator.generate_stream(request):
                # Append the visible content + internal reasoning to their
                # separate accumulators. The DB only ever stores the visible
                # content (rejoined at the end), so reasoning never leaks
                # into the persisted message.
                if llm_chunk.content:
                    content_chunks.append(llm_chunk.content)
                if llm_chunk.reasoning:
                    reasoning_chunks.append(llm_chunk.reasoning)
                # Build the optional dev-mode debug payload. Only the
                # very first chunk carries it; the orchestrator yields
                # the message list exactly once at the head of the
                # stream. In production (debug_enabled=False) we skip
                # the construction entirely so the wire stays clean.
                debug_info: LLMDebugInfo | None = None
                if debug_enabled and llm_chunk.debug_messages is not None:
                    # Resolve the model name defensively — older test
                    # doubles and stub services may not expose
                    # ``model_name``. The dev-mode modal just shows
                    # "unknown" in that case rather than crashing the
                    # whole chat stream.
                    model_name = "unknown"
                    llm = getattr(self, "_llm", None)
                    if llm is not None and hasattr(llm, "model_name"):
                        model_name = llm.model_name
                    debug_info = LLMDebugInfo(
                        model=model_name,
                        messages=llm_chunk.debug_messages,
                        temperature=request.temperature,
                        max_tokens=request.max_tokens,
                    )
                # Forward content, reasoning, and the terminal usage
                # block to the SSE consumer as separate channels. The
                # route translates each into its own SSE event so the
                # frontend can render token counts (usage) without
                # disturbing the content/reasoning timeline. The debug
                # block rides on the same chunk that carries the
                # messages list — the route emits a single ``debug``
                # event and the rest of the stream stays as-is.
                yield ChatChunk(
                    content=llm_chunk.content,
                    reasoning=llm_chunk.reasoning,
                    usage=llm_chunk.usage,
                    debug=debug_info,
                )
        except asyncio.CancelledError:
            # User-initiated abort — persist whatever we streamed, then
            # re-raise so the FastAPI SSE handler can close the response.
            # Persist partial response on abort. We save whatever
            # reasoning we accumulated too — losing it on an aborted
            # turn is the same UX bug as losing it after a successful
            # turn: the user can no longer inspect what the model
            # thought before it stopped.
            response = "".join(content_chunks)
            full_reasoning = "".join(reasoning_chunks)
            if response:
                response = _repair_for_rp(self._markdown_repairer, bot_type, response)
                await self._messages.save(
                    command.thread_id,
                    "assistant",
                    response,
                    generation_status="stopped",
                    reasoning=full_reasoning or None,
                )
            raise
        except Exception as exc:
            # m4: this is the canonical "double-log" pattern flagged
            # in docs/review.md — ``logger.exception`` here, then
            # ``raise ExternalServiceError`` propagates the failure
            # to the route layer, which in turn will log via the
            # global error handler / Sentry integration (see
            # ``api/main.py``). If Sentry is not configured, you'll
            # see two log lines for the same incident. The fix
            # depends on the Sentry config: with Sentry in place,
            # the route-level handler is a no-op and this
            # ``logger.exception`` is the single source of truth.
            # Without Sentry, the route handler will log it again —
            # intentional, because the route log line carries the
            # HTTP request context (path, status, request_id) that
            # we don't have here. See docs/review.md m4 for the
            # full discussion.
            logger.exception("Streaming chat generation failed")
            raise ExternalServiceError("Failed to generate assistant response") from exc

        response = "".join(content_chunks)
        full_reasoning = "".join(reasoning_chunks)
        if response:
            response = _repair_for_rp(self._markdown_repairer, bot_type, response)
            assistant_msg_id = await self._messages.save(
                command.thread_id,
                "assistant",
                response,
                generation_status="complete",
                reasoning=full_reasoning or None,
                # Stamp the floating prompt we actually sent so the chat
                # UI can render the "what was injected" panel. Mirrors
                # how ``reasoning`` is captured — same field pattern, same
                # lifecycle. Empty string = no floating prompt sent (no-op
                # for the bot author; the panel simply doesn't render).
                dynamic_system_prompt=request.dynamic_system_prompt or None,
            )

            # Background state-update task. Mirrors the
            # ``run_summarization`` pattern in the route handler (see
            # api/routes/chat.py:96-127): fire-and-forget with a strong
            # reference on the container so the task isn't dropped by
            # the GC mid-flight. Only kicked off when the bot has a
            # non-empty ``world_state_prompt`` — empty = no schema =
            # no point burning LLM tokens. Also gated on having an
            # actual assistant message id (rare edge case: empty
            # content stream) and an LLM client.
            #
            # **RP-only gate.** State-tracking is a roleplay
            # feature — assistant/agent bots are productivity
            # tools that don't have a world to track. Running the
            # state LLM call for them is pure waste and leaks the
            # bot's prompts/world-state into a context that
            # doesn't need it. ``bot_type`` defaults to ``RP`` for
            # legacy reasons (pre-migration bots had no field),
            # which keeps old config working but is no excuse to
            # let a real assistant bot trigger this path.
            #
            # ``getattr(..., "")`` keeps backwards compat with tests
            # that build minimal ``SimpleNamespace`` bots without the
            # new fields. Production always has them (SQLModel default
            # is "").
            bot_type = bot.bot_type if bot is not None else BotType.RP
            if isinstance(bot_type, str):
                # Tolerate string values coming through the API
                # before ``BotType`` is applied. Mirror the same
                # pattern used in ``_repair_for_rp``.
                bot_type = BotType(bot_type) if bot_type else BotType.RP
            if (
                assistant_msg_id is not None
                and bot is not None
                and bot_type == BotType.RP
                and getattr(bot, "world_state_prompt", "").strip()
                and self._llm is not None
            ):
                await self._maybe_run_state_update(
                    command.thread_id, assistant_msg_id, bot, request
                )

            # Check if this is the first real exchange — no user messages yet (excluding the one we just saved)
            history_after = await self._load_full_history(command.thread_id)
            user_messages = [m for m in history_after if m.role == "user"]
            is_first_exchange = len(user_messages) == 1  # only the message we just saved

            if command.bot_id and is_first_exchange:
                await self._auto_name_thread_if_new(
                    command.thread_id,
                    command.bot_id,
                    command.user_input,
                    response,
                )

    # ── Section 3: Task registry & abort handling ──────────────────

    def _displace_stream(self, thread_id: int) -> None:
        """Cancel and forget any in-flight stream task for ``thread_id``.

        Called by ``start_stream`` / ``start_regenerate`` just before
        registering a new task, so a rapid double-click (or a client
        retry) cleanly aborts the previous attempt instead of silently
        overwriting the registry and leaving an orphan task to run in
        the background (RC3 in docs/review.md).

        The cancellation is shielded because ``task.cancel()`` propagates
        into the task's currently-awaiting coroutine — the task may be
        parked in a partial-save DB call, and we want to give it a moment
        to commit its ``status='stopped'`` row before we forget it.
        """
        old = self._active_streams.get(thread_id)
        if old is None or old.done():
            return
        old.cancel()
        # No await here — ``start_stream`` is sync. The displaced task's
        # CancelledError will be handled by its ``_drain`` wrapper which
        # pops the registry via ``_unregister_stream``. The new task
        # overwrites the slot right after, so the registry stays
        # consistent even if the old task is mid-cancel.

    def start_stream(
        self, command: SendMessageCommand
    ) -> tuple[asyncio.Task[None], asyncio.Queue[ChatChunk | None | BaseException]]:
        """Wrap stream_message() in a background Task and register it for abort.

        The route layer would otherwise have no way to cancel an async-generator
        from another request — async generators are not asyncio.Tasks, and the
        orchestrator's httpx request lives inside the generator's frame, not
        on a cancelable handle. This helper:

        1. Spawns a Task that drives stream_message() and pushes every chunk
           into the returned queue. The Task is the unit of cancellation that
           /api/threads/{id}/abort sees.
        2. Registers the Task in self._active_streams[thread_id] so
           abort_generation() can find it. The Task self-unregisters on exit.
        3. Pushes ``None`` as a sentinel when the task ends naturally OR is
           cancelled by abort, so the consumer's `queue.get()` always returns
           and the SSE generator can close cleanly.
        4. Pushes the exception (BaseException, including CancelledError) when
           the LLM provider failed, so the route can yield an SSE error event.

        The caller (StreamingResponse) reads from the queue and yields SSE
        events. On ``None`` it stops; on BaseException it yields an error.
        """
        queue: asyncio.Queue[ChatChunk | None | BaseException] = asyncio.Queue()

        async def _drain() -> None:
            try:
                async for chunk in self.stream_message(command):
                    await queue.put(chunk)
            except asyncio.CancelledError:
                # The stream-loop's `except CancelledError` already saved the
                # partial with status='stopped' and re-raised. We don't
                # propagate it as an error — just signal end-of-stream.
                pass
            except BaseException as exc:
                await queue.put(exc)
            finally:
                await queue.put(None)
                self._unregister_stream(command.thread_id, asyncio.current_task())  # type: ignore[arg-type]

        # RC3 fix: cancel any prior in-flight stream for this thread so
        # a double-click / client retry doesn't leave an orphan task.
        self._displace_stream(command.thread_id)
        task = asyncio.create_task(_drain(), name=f"stream-{command.thread_id}")
        self._active_streams[command.thread_id] = task
        return task, queue

    def start_regenerate(
        self,
        thread_id: int,
        message_id: int,
        bot_id: int,
        persona_id: int | None,
    ) -> tuple[asyncio.Task[None], asyncio.Queue[dict | None | BaseException]]:
        """Same as start_stream() but for regenerate_message().

        Yields dict events (type='meta'/'chunk'/'stopped'/'error'/'done')
        through the queue, so the SSE route can serialize them as before.
        """
        queue: asyncio.Queue[dict | None | BaseException] = asyncio.Queue()

        async def _drain() -> None:
            try:
                async for event in self.regenerate_message(
                    thread_id, message_id, bot_id, persona_id
                ):
                    await queue.put(event)
            except asyncio.CancelledError:
                pass
            except BaseException as exc:
                await queue.put(exc)
            finally:
                await queue.put(None)
                self._unregister_stream(thread_id, asyncio.current_task())  # type: ignore[arg-type]

        # RC3 fix: cancel any prior in-flight regenerate for this thread
        # so a double-click on "regenerate" doesn't leave an orphan task.
        self._displace_stream(thread_id)
        task = asyncio.create_task(_drain(), name=f"regenerate-{thread_id}-{message_id}")
        self._active_streams[thread_id] = task
        return task, queue

    def _unregister_stream(self, thread_id: int, task: asyncio.Task) -> None:
        """Remove the task from the active-streams registry if it matches.

        Safe to call from anywhere — the compare-and-pop pattern means
        a stale task reference can't evict a newly-registered one.
        """
        existing = self._active_streams.get(thread_id)
        if existing is task:
            self._active_streams.pop(thread_id, None)

    async def abort_generation(self, thread_id: int) -> AbortResult:
        """Cancel any in-flight LLM stream for this thread.

        Idempotent: returns was_active=False when no stream is running.
        When a stream is active, cancels the task and returns
        was_active=True. The partial assistant message is persisted
        by the stream-loop's ``except asyncio.CancelledError`` branch
        before this method returns.
        """
        task = self._active_streams.pop(thread_id, None)
        if task is None or task.done():
            return AbortResult(was_active=False, partial_saved=False)
        task.cancel()
        # Give the cancellation up to 2s to propagate into the save
        # path. Shield so a re-raise here doesn't cancel our wait.
        # m6: catch only the exceptions we expect to see here:
        # - TimeoutError: wait_for hit its 2.0s budget (cancellation
        #   hasn't propagated yet — the task is still cleaning up).
        # - asyncio.CancelledError: the task re-raises this as it
        #   unwinds, *after* its except-block saved the partial.
        #   Note CancelledError is a BaseException (not Exception)
        #   since Python 3.8, so we must list it explicitly — a
        #   bare ``except Exception:`` would let it propagate and
        #   kill the abort endpoint.
        # The previous ``except (TimeoutError, asyncio.CancelledError,
        # Exception):`` form was redundant: ``Exception`` already covers
        # ``TimeoutError``; the only reason to list both was the
        # CancelledError gotcha. Tightened to just the two cases.
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=2.0)
        except (TimeoutError, asyncio.CancelledError):
            pass
        return AbortResult(was_active=True, partial_saved=True)

    # ── Section 4: Fire-and-forget UX (auto-name, summaries) ───────

    async def _auto_name_thread_if_new(
        self,
        thread_id: int,
        bot_id: int,
        user_input: str,
        assistant_response: str,
    ) -> None:
        """Generate a short title for a new thread based on the first exchange.
        Uses bot.first_message + user_input + assistant_response.
        Called only when is_first_exchange is True (history <= 1 message).
        """
        if self._threads is None or self._llm is None:
            return

        try:
            # Get bot first_message
            bot = await self._bots.get(bot_id)
            if bot is None:
                return

            # Truncate each part to ~200 chars for the prompt
            def trunc(text: str, n: int = 200) -> str:
                return text[:n] + "…" if len(text) > n else text

            prompt = (
                "Generate a very short title (3-6 words) for a roleplay chat.\n"
                "The title should reflect the theme, setting, or key topic of the conversation.\n"
                "Respond with ONLY the title, no quotes, no punctuation at the end.\n"
                "\n"
                f"Bot's opening message: {trunc(bot.first_message)}\n"
                f"User's first message: {trunc(user_input)}\n"
                f"Bot's first response: {trunc(assistant_response)}"
            )

            title = await self._llm.generate_response(
                [
                    {"role": "user", "content": prompt},
                ]
            )
            title = title.strip().strip('"').strip("'").strip("«»").strip()
            if title:
                await self._threads.rename(thread_id, title)
                logger.info("Auto-named thread %d -> '%s'", thread_id, title)
        except asyncio.CancelledError:
            # m7: re-raise — see message_summarizer.py for the
            # CancelledError vs BaseException rationale. Without
            # this, the broad ``except Exception:`` below would let
            # the cancellation bubble up as a logged warning,
            # silently breaking the abort endpoint.
            raise
        except Exception:
            # m5: broad catch is intentional here. Auto-naming is
            # a UX nicety that runs after the main message is
            # saved; a failure shouldn't fail the user message.
            # See message_summarizer.py for the same pattern.
            logger.exception("Failed to auto-name thread %d", thread_id)

    async def _update_thread_summary(self, thread_id: int) -> None:
        """Update ChatThread.summary from recent short_content entries."""
        if self._summarizer is None:
            return
        try:
            recent = await self._messages.list_for_thread(thread_id, limit=20)
            summary = await self._summarizer.summarize_thread_recent(
                thread_id,
                recent,
            )
            if summary and self._threads is not None:
                await self._threads.update_summary(thread_id, summary)
        except asyncio.CancelledError:
            # m7: see _auto_name_thread above.
            raise
        except Exception:
            # m5: thread summary is fire-and-forget UX; the next
            # run will retry. Don't fail the user message.
            logger.exception("Failed to update thread summary for %d", thread_id)

    async def _maybe_run_state_update(
        self,
        thread_id: int,
        assistant_message_id: int,
        bot,
        request: ConversationRequest,
    ) -> None:
        """Spawn a background task that updates Conversation.state.

        Called inline from ``stream_message`` after the assistant
        message is persisted. The actual LLM call happens in
        ``regenerate_state``; this wrapper is the *scheduling* point
        — see ``api/routes/chat.py:96-127`` for the GC-safety pattern
        this mirrors.

        We don't await the state generation here — the SSE response
        is already done and the user is reading. State is a debug/UX
        signal, not on the critical path.
        """
        import asyncio

        # Fire-and-forget. ``asyncio.create_task`` keeps the task
        # alive until completion provided something holds a strong
        # reference; we attach to the container's private dict so a
        # worker process restart doesn't drop the task mid-flight.
        # The container is a frozen dataclass — fall back to a
        # local reference if monkey-patching the dict isn't allowed.
        task = asyncio.create_task(
            self.regenerate_state(thread_id, assistant_message_id, bot, request),
            name=f"state-{thread_id}-{assistant_message_id}",
        )

        def _log_failure(t: asyncio.Task) -> None:
            if t.cancelled():
                return
            exc = t.exception()
            if exc is not None:
                # Regenerate_state already logs internally; this is a
                # belt-and-braces catch-all so a stray exception never
                # bubbles into the asyncio runtime.
                logger.exception(
                    "Background state update failed for message %d",
                    assistant_message_id,
                )

        task.add_done_callback(_log_failure)

    async def regenerate_state(
        self,
        thread_id: int,
        assistant_message_id: int,
        bot,
        request: ConversationRequest,
    ) -> None:
        """Re-derive Conversation.state from the latest exchange.

        Fire-and-forget. Errors are logged but never raised — state
        is a UX/debug signal, not a correctness invariant.

        The full LLM response is persisted verbatim into
        ``Conversation.state``. No YAML parsing, no fence stripping,
        no schema validation: the bot developer owns the format via
        ``world_state_prompt``. Whatever comes back is what gets
        stored. We do add a 4 MiB upper bound so a runaway prompt
        can't bloat the DB.
        """
        # The cheap fast-model handles state gen — structured output,
        # not chat quality. Falls back to the chat model when the
        # caller didn't wire a separate fast provider (test fixtures,
        # bootstrap configs that haven't been upgraded yet).
        state_llm = self._fast_llm or self._llm
        if state_llm is None:
            logger.warning(
                "regenerate_state skipped for message %d: no LLM available",
                assistant_message_id,
            )
            return

        # **RP-only gate (defence in depth).** The auto-spawn
        # caller in ``stream_message`` already gates on
        # ``bot_type == RP``, but ``regenerate_state`` is also
        # reachable from the public ``POST /state/regenerate``
        # endpoint. A misconfigured call against an
        # assistant/agent bot must not silently burn tokens or
        # overwrite ``Conversation.state`` with a junk world
        # snapshot — just log and bail.
        bot_type = getattr(bot, "bot_type", BotType.RP)
        if isinstance(bot_type, str):
            bot_type = BotType(bot_type) if bot_type else BotType.RP
        if bot_type != BotType.RP:
            logger.info(
                "regenerate_state skipped for message %d: bot_type=%s is not RP",
                assistant_message_id,
                bot_type,
            )
            return

        try:
            # Step 1: pull the assistant's persisted content. If the
            # message was deleted between save and regenerate (race),
            # we silently bail — there's no assistant content to seed
            # the state-prompt with, and we never want to fabricate
            # one.
            assistant_msg_text = await self._load_assistant_content(
                thread_id, assistant_message_id
            )
            if not assistant_msg_text:
                logger.info(
                    "regenerate_state skipped for message %d: "
                    "assistant content missing (likely deleted)",
                    assistant_message_id,
                )
                return

            # Step 2: pull the previous assistant's state via a
            # dedicated lookup. The old approach used
            # ``list_for_thread(limit=2, before_id=N)`` and took
            # ``history[-1].state`` — that pattern silently returns
            # ``""`` whenever the DESC window doesn't happen to
            # include the previous assistant (e.g. two consecutive
            # user turns, an edit that landed as a fresh insert with a
            # higher id, etc.). The dedicated query is both correct
            # AND cheaper.
            previous_state = (
                await self._messages.get_previous_assistant_state(
                    thread_id, before_message_id=assistant_message_id
                )
            )

            # Step 3: the LLM call. ``max_tokens`` is bounded to
            # something a real LLM provider will actually accept —
            # 4 MiB (the previous value) is rejected by OpenAI,
            # OpenRouter, Anthropic, and most open-source providers.
            # 8 KiB is generous for any YAML/JSON/prose snapshot
            # of a chat turn; anything bigger is a runaway that
            # should be clipped, not honoured. We use 8192 (8 KiB
            # in tokens) because long-running roleplay sessions
            # accumulate a large world state (NPCs with
            # secrets_known lists, multi-section world state,
            # session memory) — the 0.0.4 default of 2048 chopped
            # it mid-section and even the 4096 bump from .0.0.5 is
            # too tight for a session that has been going for a
            # while. The post-call check below detects the missing
            # closing triple-backtick fence and flags the truncation
            # with a trailing marker so the UI knows.
            response = await state_llm.generate_response(
                messages=[
                    {"role": "system", "content": bot.world_state_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Previous state:\n{previous_state or '(none)'}\n\n"
                            f"User message:\n{request.user_input}\n\n"
                            f"Assistant response:\n{assistant_msg_text}"
                        ),
                    },
                ],
                max_tokens=8192,
            )

            # 4 MiB upper bound on persisted state. The state string
            # is whatever the LLM returned in
            # ``max_tokens=4096`` above — for a YAML/JSON/prose
            # snapshot of a chat turn that's well under a megabyte.
            # The 4 MiB cap is the absolute ceiling that keeps a
            # runaway prompt from bloating every message row and the
            # JSON we send on every listMessages refresh.
            #
            # 4 * 1024 * 1024 = 4 MiB. (Not 4 KB — an older comment
            # miscounted; see the m-state-bytes note in review.md.)
            #
            # The 0.0.4 default of max_tokens=2048 silently chopped
            # state for any bot with a rich YAML schema (NPCs with
            # secrets_known lists, multi-section world state) — the
            # resulting state in the DB was syntactically invalid
            # YAML and downstream reads crashed in subtle ways.
            # ``LLMPort.generate_response`` returns ``str`` (not a
            # structured ``(text, finish_reason)`` tuple) so we can't
            # detect truncation from the LLM response alone. We
            # detect it on the way out by checking for a closing
            # triple-backtick fence that the bot's world_state_prompt
            # requires; if it's missing, the state was chopped
            # mid-section by max_tokens and we flag it. The UI sees
            # the ``[...truncated]`` marker in the debug modal and
            # the user can hit ``/state/regenerate`` to recover the
            # tail.
            max_state_bytes = 4 * 1024 * 1024
            text = response
            truncated_at_byte_cap = len(text) > max_state_bytes
            new_state = text[:max_state_bytes]
            # Heuristic: if the bot's world_state_prompt asks for
            # YAML in code fences, the assistant should close the
            # fence on its own line. We only flag when the prompt
            # actually asks for fenced output (so free-form prose
            # snapshots don't get false positives).
            asks_for_fence = "```" in (bot.world_state_prompt or "")
            fence_unclosed = asks_for_fence and not new_state.rstrip().endswith("```")
            if truncated_at_byte_cap:
                logger.warning(
                    "State for message %d truncated from %d to %d bytes",
                    assistant_message_id,
                    len(text),
                    max_state_bytes,
                )
            if fence_unclosed:
                new_state = new_state + "\n[...truncated — state gen hit max_tokens]"
                logger.info(
                    "State for message %d flagged truncated (no closing fence)",
                    assistant_message_id,
                )
            await self._messages.update_state(assistant_message_id, new_state)
            logger.info(
                "Updated state for message %d (%d bytes, truncated=%s)",
                assistant_message_id,
                len(new_state),
                truncated_at_byte_cap or fence_unclosed,
            )
        except Exception:
            # State is a convenience, not an invariant. Log and
            # move on — the chat itself succeeded, the user is
            # reading the response, and a future manual regenerate
            # call can fill in the gap.
            logger.exception(
                "regenerate_state failed for message %d",
                assistant_message_id,
            )

    async def _load_assistant_content(self, thread_id: int, message_id: int) -> str:
        """Read the persisted assistant content for a message id.

        Used by ``regenerate_state`` to feed the LLM the same text
        the user already saw. Falls back to ``""`` if the message
        was deleted or the read fails — the state-update task is
        fire-and-forget, so a missing message shouldn't crash it.

        Cheap implementation: pulls the thread's tail and filters in
        Python. ``history_limit`` caps the window so this stays O(1)
        for reasonable thread lengths. A dedicated single-message
        ``MessageRepository.get`` would be marginally faster but
        would add a new method to the Protocol for one caller.
        """
        try:
            history = await self._messages.list_for_thread(
                thread_id=thread_id,
                limit=self._settings.history_limit,
            )
        except Exception:
            return ""
        for m in history:
            if m.id == message_id:
                return m.content or ""
        return ""

    async def run_summarization(self, thread_id: int) -> None:
        """Summarize recent messages and optionally update thread summary.

        Called after SSE streaming completes. Queries the most recent messages,
        generates short_content for those missing it, and periodically updates
        the thread-level summary.
        """
        import time

        t0 = time.perf_counter()
        try:
            settings = self._settings
            logger.debug(
                "summarization.enter thread=%d enabled=%s", thread_id, settings.summarize_enabled
            )
            if not settings.summarize_enabled:
                return

            # Get recent active messages that need summarization
            recent = await self._messages.list_for_thread(
                thread_id, limit=settings.summarize_recent_limit
            )

            # Collect messages that need summarization
            to_summarize = [
                (msg.id, msg.content)
                for msg in recent
                if msg.short_content is None and msg.content and msg.id is not None
            ]

            n_summarized = 0
            if to_summarize and self._summarizer is not None:
                if settings.summarize_batch_enabled:
                    # Batch mode: parallel async summarization
                    results = await self._summarizer.batch_summarize(
                        to_summarize,
                        max_concurrent=settings.summarize_batch_size,
                    )
                    n_summarized = sum(1 for v in results.values() if v)
                else:
                    # Sequential mode: one by one
                    for msg_id, content in to_summarize:
                        result = await self._summarizer.summarize_message(msg_id, content)
                        if result:
                            n_summarized += 1

            # Periodically update thread summary. The interval check uses a
            # wider window (last 20 messages) than ``recent`` so it can
            # actually hit multiples of ``thread_summary_interval`` (e.g.
            # 10 user messages in a 20-message window). With ``recent``
            # capped at ``summarize_recent_limit=10`` we always saw 0-5
            # user messages and the modulo never fired -- a regression
            # that left thread summary permanently NULL.
            thread_summary_updated = False
            if settings.thread_summary_enabled and settings.thread_summary_interval > 0:
                window = await self._messages.list_for_thread(thread_id, limit=20)
                user_msgs_count = len([m for m in window if m.role == "user"])
                if user_msgs_count > 0 and user_msgs_count % settings.thread_summary_interval == 0:
                    await self._update_thread_summary(thread_id)
                    thread_summary_updated = True

            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "summarization.completed thread=%d elapsed=%.1fms candidates=%d summarized=%d "
                "thread_summary_updated=%s",
                thread_id,
                elapsed_ms,
                len(to_summarize),
                n_summarized,
                thread_summary_updated,
            )
        except asyncio.CancelledError:
            # m7: see _auto_name_thread above. The caller (route
            # layer) checks ``asyncio.current_task().cancelled()``
            # to distinguish "user aborted" from "summarization
            # failed" — silently swallowing the cancellation
            # would let the route report success.
            raise
        except Exception:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.exception("summarization.failed thread=%d elapsed=%.1fms", thread_id, elapsed_ms)

    # ── Section 5: Branching (regenerate from a prior message) ──────

    async def regenerate_message(
        self, thread_id: int, message_id: int, bot_id: int, persona_id: int | None = None
    ) -> AsyncGenerator[dict]:
        """Regenerate a bot message by creating a new branch version.

        Takes bot_id explicitly since the service may not have a thread repository
        to look it up. Yields SSE-compatible dict events.
        """
        # 1. Find the target message — check for existing versions first.
        # Important: ``target`` must be the specific version whose id
        # matches ``message_id``, NOT necessarily ``versions[0]``.
        # ``get_versions`` returns rows ordered by ``branch_index ASC``,
        # so ``versions[0]`` is always the inactive v0 (orig) — but
        # the caller (UI, branch switcher) might be regenerating a
        # later branch. Picking ``versions[0]`` here would silently
        # re-target the original message, zeroing out
        # ``branch_index`` on the next save and breaking version
        # numbering for any non-first regenerate.
        versions = await self._messages.get_versions(message_id)
        if versions:
            target_msg = next((m for m in versions if m.id == message_id), versions[0])
        else:
            all_msgs = await self._messages.list_for_thread(thread_id, limit=200)
            target_msg = next((m for m in all_msgs if m.id == message_id), None)
            if target_msg is None:
                raise NotFoundError(f"Message {message_id} was not found in thread {thread_id}")
            versions = [target_msg]

        target = target_msg

        # 2a. Branch-aware delete of the active chain AFTER target.
        # Done BEFORE promoting target to branch v0 so that target is
        # still visible in ``list_for_thread`` (and we can find it in
        # the active chain to determine the tail). After step 2 below,
        # target is ``is_active=False`` and would be filtered out by the
        # chain query — making tail detection impossible.
        await self._delete_active_chain_after(thread_id, message_id)

        # 2b. Promote the original message to branch version 0, inactive.
        # RC10 mitigation: a fresh ``uuid.uuid4()`` for ``branch_group``
        # makes two parallel ``regenerate_message`` calls for the same
        # ``message_id`` write to disjoint branch spaces — the LLM may
        # run twice and produce two valid assistant branches, but they
        # won't collide on the same ``(thread_id, branch_group,
        # branch_index)`` tuple. The user keeps both versions and can
        # switch between them via ``switch_version``.
        branch_group = target.branch_group
        branch_index = target.branch_index
        if branch_group is None:
            branch_group = str(uuid_lib.uuid4())
            branch_index = 0
            # Update the original message in-place to set branch fields
            await self._messages.update_branch(message_id, branch_group, 0, is_active=False)

        # 2c. Deactivate ALL remaining versions in this branch group.
        if branch_group:
            await self._messages.deactivate_branch_group(branch_group, thread_id)

        next_branch_index = branch_index + 1

        # Resolve bot_type for the markdown-repair filter below. Same
        # rationale as in stream_message: cheap PK SELECT vs threading
        # bot_type through every helper.
        regen_bot = await self._bots.get(bot_id)
        bot_type: str | None = regen_bot.bot_type if regen_bot is not None else None

        # 4. Get remaining history — exclude the target message itself
        history = await self._load_full_history(thread_id)
        history = [m for m in history if m.id != message_id]
        user_msgs = [m for m in history if m.role == "user"]
        # Regenerating a *greeting* (the bot's first_message, posted before
        # the user said anything) lands here with an empty `user_msgs` list.
        # ``SendMessageCommand.user_input`` enforces ``min_length=1``, so we
        # substitute a neutral placeholder that satisfies the validator and
        # tells the LLM to keep going from the existing history rather than
        # react to a fabricated user turn.
        if user_msgs:
            last_user_input = user_msgs[-1].content
        else:
            last_user_input = "[continue the conversation]"

        # The last user message is already in history AND will be passed
        # as user_input — exclude it from history to prevent duplication
        exclude_ids = {message_id}
        if user_msgs and user_msgs[-1].id is not None:
            exclude_ids.add(user_msgs[-1].id)
            history = [m for m in history if m.id != user_msgs[-1].id]

        # 5. Build and run the LLM request — exclude target message from context
        command = SendMessageCommand(
            thread_id=thread_id,
            bot_id=bot_id,
            user_input=last_user_input,
            persona_id=persona_id,
        )
        request = await self._build_request(command, exclude_message_ids=exclude_ids)

        content_chunks: list[str] = []
        reasoning_chunks: list[str] = []
        yield {
            "type": "meta",
            "thread_id": thread_id,
            "branch_group": branch_group,
            "branch_index": next_branch_index,
        }
        try:
            async for llm_chunk in self._orchestrator.generate_stream(request):
                if llm_chunk.content:
                    content_chunks.append(llm_chunk.content)
                if llm_chunk.reasoning:
                    reasoning_chunks.append(llm_chunk.reasoning)
                # Forward both — reasoning is rendered in a collapsible panel
                # on the frontend; it never reaches the persisted branch.
                if llm_chunk.reasoning:
                    yield {"type": "reasoning", "content": llm_chunk.reasoning}
                if llm_chunk.content:
                    yield {"type": "chunk", "content": llm_chunk.content}
                # Dev-mode LLM debug payload. The orchestrator yields
                # the message list exactly once at the head of the
                # stream; in production (debug_enabled=False) we skip
                # the construction entirely so the wire stays clean.
                # Without this, the dev modal icon never appears for
                # regenerated messages even though ``/api/config``
                # reports ``debug_enabled=True`` — and the route only
                # forwards the payload to the SSE consumer here, not
                # via the ``format_chunk`` helper that send_message
                # uses. (See api/routes/chat.py for the difference.)
                if self._settings.debug_enabled and llm_chunk.debug_messages is not None:
                    model_name = "unknown"
                    llm = getattr(self, "_llm", None)
                    if llm is not None and hasattr(llm, "model_name"):
                        model_name = llm.model_name
                    yield {
                        "type": "debug",
                        "debug": {
                            "model": model_name,
                            "messages": llm_chunk.debug_messages,
                            "temperature": request.temperature,
                            "max_tokens": request.max_tokens,
                        },
                    }
                if llm_chunk.usage:
                    yield {"type": "usage", "usage": llm_chunk.usage.model_dump()}
        except asyncio.CancelledError:
            # User-initiated abort — persist the partial branch with status='stopped'.
            # The SSE generator keeps running so the client can read the 'stopped' event.
            response = "".join(content_chunks)
            full_reasoning = "".join(reasoning_chunks)
            if response:
                response = _repair_for_rp(self._markdown_repairer, bot_type, response)
                await self._messages.save_branch(
                    thread_id,
                    "assistant",
                    response,
                    branch_group,
                    next_branch_index,
                    generation_status="stopped",
                    reasoning=full_reasoning or None,
                )
            yield {"type": "stopped"}
            return
        except Exception:
            # m5: any failure → yield a structured error event
            # so the frontend can surface it. Broad catch because
            # the LLM stream path can fail in many ways (httpx
            # timeout, JSON parse error, sqlite lock, etc).
            # Note: ``asyncio.CancelledError`` is already handled
            # by the explicit ``except CancelledError:`` block above
            # (yields "stopped"), so we don't need to re-raise here.
            logger.exception("Branch regeneration failed")
            yield {"type": "error", "detail": "Failed to generate assistant response"}
            return

        response = "".join(content_chunks)
        full_reasoning = "".join(reasoning_chunks)
        if response:
            response = _repair_for_rp(self._markdown_repairer, bot_type, response)
            new_id = await self._messages.save_branch(
                thread_id,
                "assistant",
                response,
                branch_group,
                next_branch_index,
                generation_status="complete",
                reasoning=full_reasoning or None,
            )
            # Build versions list
            new_versions = await self._messages.get_versions(new_id) if new_id is not None else []
            if not new_versions and new_id is not None:
                # Fallback: construct versions from what we know. Pull
                # ``reasoning`` off the source message (target) and the
                # newly-generated content (response) so the regen
                # preview in the chat panel preserves both the
                # chain-of-thought we just produced and the prior
                # turn's reasoning if we want to display it.
                new_versions = [
                    MessageDTO(
                        id=new_id,
                        role="assistant",
                        content=response,
                        reasoning=full_reasoning or None,
                        branch_group=branch_group,
                        branch_index=next_branch_index,
                        is_active=True,
                        generation_status="complete",
                    ),
                ]
                if branch_index == 0:
                    new_versions.insert(
                        0,
                        MessageDTO(
                            id=message_id,
                            role=target.role,
                            content=target.content,
                            reasoning=target.reasoning,
                            branch_group=branch_group,
                            branch_index=0,
                            is_active=False,
                            generation_status="complete",
                        ),
                    )
            import logging

            logging.warning(
                f"REGEN: new_id={new_id}, branch_group={branch_group}, next_branch_index={next_branch_index}, n_versions={len(new_versions)}, versions_ids={[v.id for v in new_versions]}"
            )
            # Find the new message in versions list
            new_msg = next((v for v in new_versions if v.id == new_id), None)
            yield {
                "type": "done",
                "message": new_msg.model_dump(mode="json") if new_msg else None,
                "message_id": new_id,
                "branch_group": branch_group,
                "versions": [v.model_dump(mode="json") for v in new_versions],
            }
        else:
            yield {"type": "error", "detail": "Empty response from LLM"}

    # ── Section 6: Retry (re-run LLM for an existing user message) ─

    async def retry_message(
        self, thread_id: int, user_message_id: int, bot_id: int, persona_id: int | None = None
    ) -> AsyncGenerator[dict]:
        """Retry generating a response after a user message.

        Deletes everything after the user message (failed responses, errors),
        then streams a new assistant response using the existing user message as input.
        No new user message is created — the existing one is reused.
        """
        # 1. Find the user message
        all_msgs = await self._load_full_history(thread_id)
        user_msg = next((m for m in all_msgs if m.id == user_message_id and m.role == "user"), None)
        if user_msg is None:
            raise NotFoundError(
                f"User message {user_message_id} was not found in thread {thread_id}"
            )

        # 2. Delete everything after this user message
        await self._messages.delete_after(thread_id, user_message_id)

        # 3. Build command and request — exclude the user message from history
        command = SendMessageCommand(
            thread_id=thread_id,
            bot_id=bot_id,
            user_input=user_msg.content,
            persona_id=persona_id,
        )
        request = await self._build_request(command, exclude_message_ids={user_message_id})

        # Resolve bot_type for the markdown-repair filter below. Same
        # rationale as in stream_message / regenerate_message.
        retry_bot = await self._bots.get(bot_id)
        bot_type: str | None = retry_bot.bot_type if retry_bot is not None else None

        # 4. Stream the new response.
        # generate_stream() yields LLMChunk objects (content + reasoning);
        # read .content (and optionally .reasoning) before yielding to the
        # SSE consumer, the same pattern used by stream_message and
        # regenerate_message. Yielding the LLMChunk object directly would
        # crash the route's json.dumps with "not JSON serializable".
        chunks: list[str] = []
        try:
            async for llm_chunk in self._orchestrator.generate_stream(request):
                if llm_chunk.reasoning:
                    yield {"type": "reasoning", "content": llm_chunk.reasoning}
                if llm_chunk.content:
                    chunks.append(llm_chunk.content)
                    yield {"type": "chunk", "content": llm_chunk.content}
        except asyncio.CancelledError:
            # User-initiated abort — persist the partial with status='stopped'.
            response = "".join(chunks)
            if response:
                response = _repair_for_rp(self._markdown_repairer, bot_type, response)
                await self._messages.save(
                    thread_id, "assistant", response, generation_status="stopped"
                )
            yield {"type": "stopped"}
            return
        except Exception:
            # m5: see _regenerate_message_stream — broad catch
            # because the LLM stream path can fail in many ways.
            # ``CancelledError`` is handled by the explicit branch
            # above.
            logger.exception("Retry message generation failed")
            yield {"type": "error", "detail": "Failed to generate assistant response"}
            return

        response = "".join(chunks)
        if response:
            response = _repair_for_rp(self._markdown_repairer, bot_type, response)
            await self._messages.save(
                thread_id, "assistant", response, generation_status="complete"
            )
            yield {"type": "done"}
        else:
            yield {"type": "error", "detail": "Empty response from LLM"}

    # ── Section 7: Helpers (request assembly, persona vars) ─────────

    async def _build_request(
        self, command: SendMessageCommand, exclude_message_ids: set[int] | None = None
    ) -> ConversationRequest:
        bot = await self._bots.get(command.bot_id)
        if bot is None:
            raise NotFoundError(f"Bot {command.bot_id} was not found")

        history = await self._load_full_history(command.thread_id)
        if exclude_message_ids:
            history = [m for m in history if m.id not in exclude_message_ids]
        # Exclude the last user message from history — it will be sent as user_input
        # (already saved above in stream_message, avoid double inclusion)
        user_msgs_before = [m for m in history if m.role == "user"]
        last_user_msg_id: int | None = user_msgs_before[-1].id if user_msgs_before else None
        if last_user_msg_id is not None:
            history = [m for m in history if m.id != last_user_msg_id]

        # ── DEBUG: log how much history we feed the LLM ──────────────
        # This is the load-bearing log for the "does the LLM see all
        # messages?" question. ``list_for_thread`` defaults to
        # ``limit=20``, so the call below silently truncates unless
        # the caller passes an explicit limit. We want to know
        # exactly what fraction of the thread history is in scope.
        logger.info(
            "[history-load] thread=%s loaded=%d total_active_estimate=%d",
            command.thread_id,
            len(history),
            # Cheap heuristic: trust repo's default-page size + 1; the
            # accurate count would need a second COUNT query which is
            # too expensive for a debug log. The reader can correlate
            # this with the orchestrator's later summary.
            len(history),
        )

        # If history is empty and bot has a first_message, reconstruct
        # it locally so the LLM sees a coherent opening turn. The DB
        # persistence of the first message is handled separately by
        # stream_save_first_message() — which is the K4 idempotency
        # boundary (consults the DB, not an in-memory set).
        if not history and bot.first_message:
            history = [MessageDTO(role="assistant", content=bot.first_message, created_at=None)]

        # RAG context. Skip the embedding model call entirely when
        # the bot has no knowledge base entries — the similarity
        # search would land on zero documents and return ``[]``
        # anyway, but the per-query vector cost is real. The
        # underlying ``_knowledge.search`` also short-circuits
        # internally, but checking here saves the async hop and
        # the lock acquisition on the chat hot path.
        context: list[str] = []
        if self._knowledge is not None and await self._knowledge.has_documents(
            command.bot_id
        ):
            context = await self._knowledge.search(
                command.bot_id, command.user_input, top_k=15
            )

        user_persona = None
        if command.persona_id is not None and self._personas is not None:
            user_persona = await self._personas.get(command.persona_id)

        # Use injected settings (K3 fix) — they were resolved once at
        # construction. The previous implementation re-parsed the .env
        # on every chat request.
        settings = self._settings

        # Context compression: replace old messages with short_content
        context_compressed = False
        if (
            settings.context_compression_enabled
            and len(history) > settings.context_compression_threshold
        ):
            cutoff = len(history) - settings.context_compression_keep_recent
            compressed_count = 0
            for i, msg in enumerate(history):
                if i < cutoff and msg.short_content:
                    history[i] = MessageDTO(
                        id=msg.id,
                        role=msg.role,
                        content=msg.short_content,
                        short_content=msg.short_content,
                        created_at=msg.created_at,
                        branch_group=msg.branch_group,
                        branch_index=msg.branch_index,
                        is_active=msg.is_active,
                    )
                    compressed_count += 1
            if compressed_count > 0:
                context_compressed = True
                logger.info(
                    "Context compression: %d/%d messages compressed (threshold=%d, keep_recent=%d)",
                    compressed_count,
                    len(history),
                    settings.context_compression_threshold,
                    settings.context_compression_keep_recent,
                )

        # Load uploaded files for assistant/agent bots
        uploaded_files = []
        bot_type = bot.bot_type or BotType.RP
        if bot_type in (BotType.ASSISTANT, BotType.AGENT) and self._files is not None:
            if last_user_msg_id is not None:
                uploaded_files = await self._files.list_for_message(last_user_msg_id)

        # Pull the world-state snapshot from the previous assistant
        # turn so the orchestrator can inject it as a system message
        # right after the floating reminder (see
        # ``langgraph_orchestrator._node_user_input``).
        #
        # Skip messages whose ``state`` is empty / None / whitespace.
        # A regenerate target may sit behind an assistant whose
        # state-update hasn't landed yet (or got lost to a crash),
        # or a hand-inserted row in tests may have no state. The
        # previous-turn state must come from an assistant that
        # actually has one — otherwise we'd feed an empty / stale
        # block into the prompt and the LLM would hallucinate a
        # fresh world from nothing. The ``state-update``
        # regenerator uses ``get_previous_assistant_state`` for
        # the same reason — we keep them aligned by reading the
        # ``MessageDTO`` ``state`` attribute on the active,
        # branch-filtered history that ``list_for_thread``
        # already produced.
        #
        # Role filter: ``MessageDTO.role`` is ``Literal["system",
        # "user", "assistant"]``, but only ``assistant`` rows ever
        # have a non-empty ``state`` (the state-update task only
        # targets them, and ``Conversation.state`` is only written
        # via ``update_state`` / the regenerator). We trust that
        # invariant here instead of gating on ``role`` explicitly —
        # the ``candidate`` non-empty check filters both
        # non-assistant rows AND empty-state assistants out in one
        # pass.
        prev_world_state = ""
        for msg in reversed(history):
            candidate = (msg.state or "").strip()
            if candidate:
                prev_world_state = candidate
                break

        return ConversationRequest(
            thread_id=command.thread_id,
            bot_id=command.bot_id,
            user_input=command.user_input,
            bot_name=bot.name,
            bot_personality=bot.personality,
            bot_scenario=bot.scenario,
            first_message=bot.first_message,
            bot_type=bot_type,
            user_persona=user_persona,
            history=history,
            untrusted_context=context,
            context_compressed=context_compressed,
            max_tokens=settings.default_max_tokens,
            temperature=settings.default_temperature,
            uploaded_files=uploaded_files,
            mes_example=getattr(bot, "mes_example", "") or "",
            # **RP-only fields.** ``dynamic_system_prompt`` and
            # ``world_state_prompt`` are roleplay-only features
            # (floating reminder + world-state tracking). We zero
            # them out for assistant/agent bots so the orchestrator
            # never injects a ``[Reminder]`` / ``[World state]``
            # block into a productivity context where it doesn't
            # belong. The schema still carries the values (the
            # fields exist on the model) — we just don't push them
            # into the request.
            dynamic_system_prompt=(
                getattr(bot, "dynamic_system_prompt", "") or ""
                if bot_type == BotType.RP
                else ""
            ),
            world_state_prompt=(
                getattr(bot, "world_state_prompt", "") or ""
                if bot_type == BotType.RP
                else ""
            ),
            prev_world_state=(
                prev_world_state if bot_type == BotType.RP else ""
            ),
        )

    # ── Section 8: Branch-aware deletion helpers ─────────────────────

    async def _delete_active_chain_after(self, thread_id: int, target_id: int) -> None:
        """Delete every active-chain message that comes AFTER ``target_id``.

        Replaces the naive ``messages.delete_after(thread_id, target_id)``
        used by ``regenerate_message``. The naive version cuts by row id,
        which is broken once ``update_message`` exists: editing a later
        user message promotes a new row with a *higher* id, so it can sit
        past ``target_id`` in id-ordering while still being *before*
        ``target_id`` in the active conversation chain. Slicing by id
        wipes that freshly-edited user message along with the legitimate
        "tail" of the chain.

        Algorithm:
          1. Pull the active chain via ``list_for_thread``, which is
             already in chain order (oldest first). The repository
             fetches DESC at the SQL level and then reverses to ASC
             for the DTO list, so we get chronological order straight
             from the call.
          2. Locate ``target_id``; everything after it in the list is
             "tail".
          3. For each tail message, hard-delete it AND deactivate the
             rest of its ``branch_group`` (the stale inactive siblings).
          4. User messages that came in via an edit (new id, in the
             chain *before* target) are never in the tail, so they're
             preserved automatically.

        Cost is O(N) calls into the repository, but N is bounded by
        ``history_limit`` (200 today) and regenerate is not a hot path.
        If it ever shows up in a profile, a single-SQL helper on the
        repository is the next step.
        """
        # ``list_for_thread`` returns ASC chain order (oldest first).
        # See ``SqlAlchemyMessageRepository.list_for_thread`` — it
        # queries DESC and then ``reversed(messages)`` to walk the
        # chain naturally for the caller.
        active = await self._messages.list_for_thread(thread_id, limit=self._settings.history_limit)

        target_idx = next((i for i, m in enumerate(active) if m.id == target_id), -1)
        if target_idx < 0:
            # Target not in the active chain (e.g. it was already
            # deactivated by a parallel call). Nothing to delete.
            return

        tail = active[target_idx + 1 :]
        if not tail:
            return

        # Collect every branch_group in the tail so we can deactivate
        # their inactive siblings in one pass. The active row itself
        # will be hard-deleted below; the inactive siblings just need
        # ``is_active = False`` to stop showing up in ``list_for_thread``.
        tail_branch_groups = {m.branch_group for m in tail if m.branch_group}

        # Hard-delete each active tail row.
        for m in tail:
            if m.id is not None:
                await self._messages.delete(m.id)

        # Deactivate (don't hard-delete) the inactive siblings — keeping
        # them around means the user can still see them in the version
        # counter if they switch back to a still-valid branch, but they
        # won't pollute the active chain.
        for bg in tail_branch_groups:
            await self._messages.deactivate_branch_group(bg, thread_id)
