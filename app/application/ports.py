"""Ports implemented by infrastructure adapters.

With SQLModel, BotRepository returns Bot (SQLModel) directly — it is both
an ORM model and a Pydantic schema. API response models (BotResponse) live
in dto.py and are constructed by service/routes as needed.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.infrastructure.llm import LLMChunk

from app.application.dto import (
    AddKnowledgeEntryCommand,
    ConversationRequest,
    KnowledgeEntryDTO,
    MessageDTO,
    RecentThreadDTO,
    ThreadDTO,
    ThreadFileDTO,
    UserPersonaDTO,
)
from app.domain.enums import BotType

if TYPE_CHECKING:
    from app.infrastructure.db.models import Bot, BotVersion


class SettingsRepository(Protocol):
    """Read/write the ``app_settings`` singleton table.

    Methods are narrow on purpose: the service layer handles
    JSON encoding, seeding, and validation; this port only
    persists what the service hands it.
    """

    async def get_bot_categories(self) -> list[str] | None:
        """Return the persisted category list, or ``None`` if the
        singleton row hasn't been created yet (caller should seed)."""
        ...

    async def set_bot_categories(self, categories: list[str], payload: str) -> None:
        """Persist ``payload`` (already JSON-encoded) as the new
        ``bot_categories_json``. ``categories`` is passed alongside
        for repositories that prefer to encode internally; callers
        MUST keep both in sync.
        """
        ...


class BotVersionRepository(Protocol):
    async def add(self, version: BotVersion) -> int: ...

    async def list_by_bot(self, bot_id: int) -> list[BotVersion]: ...

    async def get(self, version_id: int) -> BotVersion | None: ...

    async def get_max_version(self, bot_id: int) -> int:
        """Highest ``version_number`` for the bot, or 0 if none."""
        ...

    async def delete(self, version_id: int) -> None: ...


class BotRepository(Protocol):
    async def create(
        self,
        name: str,
        personality: str,
        first_message: str,
        scenario: str = "",
        description: str = "",
        avatar_path: str | None = None,
        categories: list[str] | None = None,
        bot_type: BotType = BotType.RP,
        alternate_greetings: list[str] | None = None,
        mes_example: str = "",
        dynamic_system_prompt: str = "",
        world_state_prompt: str = "",
    ) -> int: ...

    async def update(
        self,
        bot_id: int,
        name: str,
        personality: str,
        first_message: str,
        scenario: str = "",
        description: str = "",
        avatar_path: str | None = None,
        categories: list[str] | None = None,
        bot_type: BotType = BotType.RP,
        alternate_greetings: list[str] | None = None,
        mes_example: str | None = None,
        dynamic_system_prompt: str | None = None,
        world_state_prompt: str | None = None,
    ) -> None: ...

    async def get(self, bot_id: int) -> Bot | None: ...

    async def list(self) -> list[Bot]: ...

    async def delete(self, bot_id: int) -> None: ...

    async def get_with_thread_counts(self) -> list[tuple[Bot, int]]: ...


class ThreadRepository(Protocol):
    async def create(
        self, bot_id: int, name: str = "new chat", persona_id: int | None = None
    ) -> int: ...

    async def get(self, thread_id: int) -> ThreadDTO | None: ...

    async def list_for_bot(self, bot_id: int) -> list[ThreadDTO]: ...

    async def list_recent(
        self, limit: int = 20, bot_id: int | None = None
    ) -> list[RecentThreadDTO]: ...

    async def rename(self, thread_id: int, name: str) -> None: ...

    async def update_summary(self, thread_id: int, summary: str) -> None: ...

    async def delete(self, thread_id: int) -> None: ...

    async def set_persona(self, thread_id: int, persona_id: int | None) -> None:
        """Set the active persona for a thread."""
        ...

    async def find_by_bot_and_persona(
        self, bot_id: int, persona_id: int | None
    ) -> ThreadDTO | None:
        """Find the most recent thread for a (bot_id, persona_id) pair."""
        ...

    async def set_pending_greeting(self, thread_id: int, content: str) -> None:
        """Store a greeting to use as the next first_message of a thread.

        Used when the UI lets the user pick a greeting from
        ``alternate_greetings`` BEFORE the thread has any assistant message.
        The chat service consumes this when it saves the first message.
        """
        ...


class MessageRepository(Protocol):
    async def save(
        self,
        thread_id: int,
        role: str,
        content: str,
        branch_group: str | None = None,
        branch_index: int = 0,
        is_active: bool = True,
        short_content: str | None = None,
        timestamp: datetime | None = None,
        generation_status: str = "complete",
        reasoning: str | None = None,
        # Stamped by the orchestrator at stream time when the bot has a
        # non-empty ``dynamic_system_prompt`` so the chat UI can render
        # the floating-prompt panel. ``None`` = no floating prompt was
        # sent (default for bots that don't use the feature).
        dynamic_system_prompt: str | None = None,
        # Per-message world-state snapshot for assistant turns. ``None``
        # means "don't set" (column stays NULL); pass ``""`` to
        # explicitly clear an existing state. Stamped by
        # ``regenerate_state`` after each assistant turn; can also be
        # edited by the user via the EditMessageModal.
        state: str | None = None,
    ) -> int | None: ...

    async def save_exchange(
        self,
        thread_id: int,
        user_input: str,
        assistant_response: str,
        reasoning: str | None = None,
    ) -> None: ...

    async def list_for_thread(
        self,
        thread_id: int,
        limit: int = 20,
        before_id: int | None = None,
    ) -> list[MessageDTO]: ...

    async def count_active(self, thread_id: int) -> int:
        """Count the active chain of messages in ``thread_id``.

        Mirrors the ``list_for_thread`` filter: rows with no
        ``branch_group`` plus the active row of any branch group.
        Used by ``ThreadService.get_stats`` so the chat header reports
        total messages rather than the latest paginated window.

        Returns 0 for unknown / empty threads (not an error).
        """
        ...

    async def clear_thread(self, thread_id: int) -> None: ...

    async def update(self, message_id: int, content: str) -> None: ...

    async def update_state(self, message_id: int, state: str) -> None: ...

    async def get_previous_assistant_state(
        self, thread_id: int, before_message_id: int | None = None
    ) -> str:
        """Return the most recent non-empty ``Conversation.state`` for an
        assistant message in the thread, optionally restricted to
        messages with id strictly less than ``before_message_id``.

        Returns ``""`` if no such state exists (brand-new thread,
        state-update hadn't landed yet, or the bot has no
        ``world_state_prompt``).

        This is a precise lookup — unlike ``list_for_thread`` with a
        small ``limit``, it does NOT depend on the DESC window size
        accidentally including the right row. Used by
        ``ChatService.regenerate_state`` to feed the LLM the previous
        turn's state so it can mutate it rather than start from scratch.
        """
        ...

    async def update_short_content(self, message_id: int, short_content: str) -> None: ...

    async def save_first_assistant_if_absent(self, thread_id: int, content: str) -> bool:
        """Atomically persist the bot's first_message iff no assistant row exists.

        Returns True if a row was inserted, False if the thread already
        had an assistant message (or the thread doesn't exist).
        """
        ...

    async def delete(self, message_id: int) -> None: ...

    async def delete_from(self, thread_id: int, message_id: int) -> None:
        """Delete message_id and all messages after it in the thread."""
        ...

    async def save_branch(
        self,
        thread_id: int,
        role: str,
        content: str,
        branch_group: str,
        branch_index: int,
        timestamp: datetime | None = None,
        generation_status: str = "complete",
        reasoning: str | None = None,
        # World-state snapshot to copy into the new branch. ``None``
        # means "leave NULL on the new row" (matches the historical
        # behaviour where state was an opaque system attribute);
        # ``""`` explicitly clears it. The service layer is expected
        # to forward the *original* message's state here so branched
        # edits don't silently drop the world-state context the user
        # was looking at when they decided to edit.
        state: str | None = None,
        # Floating system-prompt snapshot the LLM received on this
        # turn. Stamped so the chat UI can render the "what was sent"
        # panel on regenerated messages too, matching the contract on
        # ``save``. ``None`` = no floating prompt was injected.
        dynamic_system_prompt: str | None = None,
    ) -> int | None:
        """Save a message with explicit branch group."""
        ...

    async def get_versions(self, message_id: int) -> list[MessageDTO]:
        """Get all messages in the same branch group."""
        ...

    async def switch_version(self, branch_group: str, target_version_id: int) -> None:
        """Set target_version_id is_active=True, all others in branch_group=False."""
        ...

    async def get_last_bot_message(self, thread_id: int) -> MessageDTO | None:
        """Get the last assistant message in a thread ordered by id."""
        ...

    async def get_first_assistant(self, thread_id: int) -> MessageDTO | None:
        """Get the chronologically-first assistant message in a thread."""
        ...

    async def update_content(self, message_id: int, content: str) -> None:
        """Overwrite a message's content."""
        ...

    async def update_branch(
        self,
        message_id: int,
        branch_group: str,
        branch_index: int,
        is_active: bool,
    ) -> None:
        """Update branch fields on an existing message."""
        ...

    async def delete_after(self, thread_id: int, message_id: int) -> None:
        """Delete all messages AFTER message_id (exclusive) in a thread."""
        ...

    async def deactivate_branch_group(self, branch_group: str, thread_id: int) -> None:
        """Set is_active=False for all messages in a branch group."""
        ...


class KnowledgeBaseRepository(Protocol):
    async def add(self, command: AddKnowledgeEntryCommand) -> None: ...

    async def search(self, bot_id: int, query: str, top_k: int = 3) -> list[str]: ...

    async def search_with_scores(
        self, bot_id: int, query: str, top_k: int = 5
    ) -> list[tuple[str, float]]: ...

    async def list_entries(self, bot_id: int) -> list[KnowledgeEntryDTO]: ...

    async def has_documents(self, bot_id: int) -> bool:
        """Cheap "is the KB non-empty for this bot?" probe.

        Lets the chat hot path skip the per-turn embedding model
        call when the bot has no knowledge base entries — the
        similarity search would return ``[]`` anyway, so paying
        the vector cost is pure waste. Implementations must use
        metadata-only reads (``vectorstore.get(include=[])``) and
        must NOT call the embedding function.
        """
        ...

    async def delete(self, bot_id: int, entry_id: str) -> None: ...

    async def update(self, bot_id: int, entry_id: str, content: str) -> None: ...


class LLMPort(Protocol):
    async def generate_response(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str: ...

    async def generate_response_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[LLMChunk]: ...

    @property
    def model_name(self) -> str:
        """Resolved model name (override or settings default).

        Read by the orchestrator when building the dev-mode debug
        payload so the modal can show which model actually served the
        request. Implementations must return the same value the next
        ``generate_response*`` call would dispatch to.
        """
        ...


class ConversationOrchestratorPort(Protocol):
    async def generate(self, request: ConversationRequest) -> str: ...

    async def generate_stream(self, request: ConversationRequest) -> AsyncGenerator[LLMChunk]: ...


class BotPreambleProvider(Protocol):
    """M5: source of the per-bot-type system preamble.

    Replaces the module-level ``BOT_TYPE_PREAMBLES`` dict that was
    hard-coded in the langgraph orchestrator. The provider pattern lets
    us:

    * Override individual types via ``Settings.preamble_overrides`` (a
      ``dict[BotType.value, str]`` parsed from env JSON).
    * Replace the whole preamble set in tests with a stub.
    * Add a future DB-backed or per-bot preamble without changing the
      orchestrator.

    The default implementation is built in
    ``app.infrastructure.orchestration.preambles``; the orchestrator
    constructs it lazily if no provider is injected.
    """

    def get(self, bot_type: BotType) -> str: ...

    def fallback(self) -> str:
        """Return the preamble used when ``bot_type`` is unknown."""
        ...


class MarkdownRepairer(Protocol):
    """Repair broken markdown formatting in LLM output.

    Used by ``ChatService`` after the LLM stream is collected, but
    only for bots whose ``bot_type`` is ``RolePlay``. The repair runs
    on the final assembled ``response`` string before it is
    persisted via ``MessageRepository.save`` /
    ``save_branch``, so the SSE stream the client sees during
    generation is untouched — only what lands in the database is
    cleaned up.

    The narrow scope (emphasis markers + fenced code blocks only)
    and the explicit ``mode`` parameter mirror the public API of
    the ``format-standart-rp`` library. Keeping the port narrow
    means the service can ask for ``"close"`` or ``"strip"``
    without leaking implementation details.
    """

    def repair(self, text: str, mode: str = "close") -> str:
        """Return ``text`` with unclosed markdown markers repaired.

        ``mode`` is ``"close"`` (default) to append missing closing
        markers, or ``"strip"`` to remove unclosed markers
        entirely. Unknown modes raise ``ValueError``.
        """
        ...


class PersonaRepository(Protocol):
    async def create(
        self,
        name: str,
        description: str = "",
        avatar_path: str | None = None,
    ) -> int: ...

    async def update(
        self,
        persona_id: int,
        name: str,
        description: str = "",
        avatar_path: str | None = None,
    ) -> None: ...

    async def get(self, persona_id: int) -> UserPersonaDTO | None: ...

    async def list(self) -> list[UserPersonaDTO]: ...

    async def delete(self, persona_id: int) -> None: ...


class ThreadFileRepository(Protocol):
    async def save(
        self,
        thread_id: int,
        filename: str,
        file_type: str,
        storage_path: str,
        extracted_text: str | None = None,
    ) -> ThreadFileDTO: ...

    async def list_for_thread(self, thread_id: int) -> list[ThreadFileDTO]: ...

    async def get(self, file_id: int) -> ThreadFileDTO | None: ...

    async def delete(self, file_id: int) -> None: ...

    async def delete_by_thread(self, thread_id: int) -> None: ...

    async def attach_to_message(self, file_ids: list[int], message_id: int) -> None: ...

    async def list_for_message(self, message_id: int) -> list[ThreadFileDTO]: ...


class UploadedFile(Protocol):
    """Framework-independent view of an incoming uploaded file.

    ``UploadService.upload`` depends on this protocol rather than on
    ``fastapi.UploadFile`` so the application layer stays free of
    HTTP-framework imports (review2.md: app/application must not
    import fastapi). The FastAPI route adapts its ``UploadFile`` to
    this shape with a thin shim, and other presentation layers (CLI,
    tests) can implement it directly.
    """

    @property
    def filename(self) -> str | None:
        """Original filename supplied by the client, or ``None``."""
        ...

    @property
    def size(self) -> int | None:
        """Client-declared size, or ``None`` if not provided.

        Treated as advisory only — ``UploadService`` re-enforces the
        cap while reading the stream.
        """
        ...

    def read(self, size: int = -1) -> bytes:
        """Read up to ``size`` bytes; ``-1`` reads everything available."""
        ...


class TTSProvider(Protocol):
    """Provider-agnostic text-to-speech synthesis.

    Implementations wrap a specific HTTP API (MiniMax ``/v1/t2a_v2``,
    OpenAI TTS, local Piper, etc.) and return raw audio bytes — usually
    MP3, sometimes WAV. The :class:`TTSService` sits above this port and
    owns caching, hashing, and the ``cache_id`` that the API route hands
    to the client.

    Failure modes: implementations MUST raise the framework-native
    exception (``httpx.HTTPError``, ``RuntimeError``) on transport or
    provider-side errors. ``TTSService`` rewraps these as
    ``TTSError`` so callers never need to know about the underlying
    transport.
    """

    async def synthesize(
        self,
        text: str,
        voice_id: str,
        model: str,
        *,
        speed: float = 1.0,
    ) -> bytes:
        """Synthesise ``text`` and return the raw audio bytes.

        ``voice_id`` and ``model`` are opaque to the port — the service
        passes through whatever the operator configured. ``speed`` is
        a 0.5..2.0 multiplier that some providers accept; providers
        that don't support it should ignore it (don't error).
        """
        ...
