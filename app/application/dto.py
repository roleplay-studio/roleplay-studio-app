"""Pydantic DTOs used at application boundaries.

SQLModel models (in app.infrastructure.db.models) are the primary data carriers
for internal use. This module keeps only API-specific response models (where
SQLModel serialization doesn't match the frontend contract, e.g. categories as
list[str] instead of JSON string) and command DTOs.
"""

from __future__ import annotations

import json
import typing
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import BotType

if typing.TYPE_CHECKING:
    from app.infrastructure.db.models import Bot

# ── Predefined bot categories ───────────────────────────────────────
# The runtime list now lives in the ``app_settings`` singleton table
# (see ``app.application.services.settings``). The literal list below
# is the **seed** for first-run installs and remains the user-editable
# default until the user makes their first change. Keep the values
# stable across releases — they're on-disk legacy data once seeded.

DEFAULT_BOT_CATEGORIES: list[str] = [
    "Anime",
    "Game",
    "Fantasy",
    "Sci-Fi",
    "Modern",
    "Historical",
    "Romance",
    "Horror",
    "Comedy",
    "Adventure",
    "Custom",
]

# Back-compat alias for any out-of-tree imports. Will be removed once
# the next minor version ships. ``SettingsService`` no longer reads
# this constant directly — it seeds the DB instead — so it lives
# here only as documentation.
BOT_CATEGORIES = DEFAULT_BOT_CATEGORIES

# ── Bot API response (categories as list[str], not JSON string) ──────


class BotResponse(BaseModel):
    """API response model for a bot.

    SQLModel Bot stores categories as a JSON string. This response model
    deserializes it to a proper list[str] for the frontend contract.

    ``categories_invalid`` lists the entries in ``categories`` that
    are no longer defined in the configured category list. The
    frontend surfaces those as warning chips and offers a "remove"
    shortcut, but the raw ``categories`` is left untouched so the
    bot keeps its on-disk history intact until the user commits a
    cleanup. Defaults to empty list — older callers that built
    BotResponse by hand still get a valid payload.
    """

    id: int
    name: str
    personality: str = ""
    first_message: str = ""
    scenario: str = ""
    description: str = ""
    avatar_path: str | None = None
    categories: list[str] = Field(default_factory=list)
    categories_invalid: list[str] = Field(default_factory=list)
    thread_count: int = 0
    bot_type: str = "rp"
    alternate_greetings: list[str] = Field(default_factory=list)
    mes_example: str = ""

    @classmethod
    def from_orm_bot(
        cls,
        bot: Bot,
        thread_count: int = 0,
        valid_categories: set[str] | None = None,
    ) -> BotResponse:
        """Build an API response from a SQLModel Bot instance.

        ``valid_categories`` is the current user-defined category
        list. When supplied, every entry in ``bot.categories`` is
        cross-referenced and orphaned values land in
        ``categories_invalid`` (raw ``categories`` is left
        unchanged). When ``None`` (e.g. legacy test fixtures),
        ``categories_invalid`` defaults to empty so the existing
        contract is preserved.
        """
        cats: list[str] = []
        if isinstance(bot.categories, str):
            try:
                parsed = json.loads(bot.categories)
                cats = parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                cats = []
        elif isinstance(bot.categories, list):
            cats = bot.categories

        alt_greetings: list[str] = []
        alt_raw = getattr(bot, "alternate_greetings", "[]")
        if isinstance(alt_raw, str):
            try:
                parsed = json.loads(alt_raw)
                alt_greetings = parsed if isinstance(parsed, list) else []
            except (json.JSONDecodeError, TypeError):
                alt_greetings = []
        elif isinstance(alt_raw, list):
            alt_greetings = alt_raw

        invalid: list[str] = []
        if valid_categories is not None and cats:
            invalid = [c for c in cats if c not in valid_categories]

        return cls(
            id=bot.id,
            name=bot.name,
            personality=bot.personality or "",
            first_message=bot.first_message or "",
            scenario=bot.scenario or "",
            description=bot.description or "",
            avatar_path=bot.avatar_path,
            categories=cats,
            categories_invalid=invalid,
            thread_count=thread_count,
            bot_type=bot.bot_type or BotType.RP,
            alternate_greetings=alt_greetings,
            mes_example=getattr(bot, "mes_example", "") or "",
        )


# ── Message DTO (used internally and in API) ──────────────────────────


class MessageDTO(BaseModel):
    id: int | None = None
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)
    short_content: str | None = None  # краткая суммаризация сообщения
    # Chain-of-thought emitted by reasoning-capable LLMs. ``None`` for
    # messages that never went through a reasoning model (or older rows
    # created before the column existed). The frontend hides the
    # reasoning panel when this is missing/empty.
    reasoning: str | None = None
    created_at: datetime | None = None
    branch_group: str | None = None
    branch_index: int = 0
    is_active: bool = True
    generation_status: str = "complete"
    versions: list[MessageDTO] = Field(default_factory=list)  # all versions of this branch group


class UpdateMessageCommand(BaseModel):
    message_id: int
    content: str = Field(min_length=1)


class AbortResult(BaseModel):
    was_active: bool
    partial_saved: bool = False


# ── Thread DTOs ─────────────────────────────────────────────────────


class ThreadDTO(BaseModel):
    id: int
    bot_id: int
    name: str
    summary: str | None = None
    persona_id: int | None = None
    persona_name: str | None = None
    created_at: datetime | None = None


class RecentThreadDTO(BaseModel):
    """A thread with bot info, persona name, and last message preview."""

    thread_id: int
    bot_id: int
    bot_name: str
    bot_avatar_path: str | None = None
    bot_categories: list[str] = Field(default_factory=list)
    bot_personality: str = ""
    persona_name: str | None = None
    persona_avatar_path: str | None = None
    last_message_preview: str = ""
    summary: str | None = None
    last_message_at: datetime | None = None


# ── Bot commands ────────────────────────────────────────────────────


class CreateBotCommand(BaseModel):
    name: str = Field(min_length=1)
    personality: str = Field(min_length=1)
    first_message: str = ""
    scenario: str = ""
    description: str = ""
    avatar_path: str | None = None
    categories: list[str] = Field(default_factory=list)
    bot_type: str = "rp"
    alternate_greetings: list[str] = Field(default_factory=list)
    mes_example: str = ""


class UpdateBotCommand(CreateBotCommand):
    bot_id: int  # No default!


# ── Chat ────────────────────────────────────────────────────────────


class SendMessageCommand(BaseModel):
    thread_id: int
    bot_id: int
    user_input: str = Field(min_length=1)
    persona_id: int | None = None
    file_ids: list[int] = Field(default_factory=list)


class AddKnowledgeEntryCommand(BaseModel):
    bot_id: int
    content: str = Field(min_length=1)
    metadata: dict[str, object] = Field(default_factory=dict)


class UpdateKnowledgeEntryCommand(BaseModel):
    bot_id: int
    entry_id: str
    content: str = Field(min_length=1)


class KnowledgeEntryDTO(BaseModel):
    id: str
    content: str
    source_type: str = "manual"  # 'manual' or 'file'
    file_name: str | None = None
    chunk_count: int | None = None  # total chunks from the same file


class AddKnowledgeFileCommand(BaseModel):
    bot_id: int
    file_content: bytes
    file_name: str
    mime_type: str = "text/plain"


class ChatResponse(BaseModel):
    content: str


class LLMDebugInfo(BaseModel):
    """Dev-mode debug payload for a single LLM request.

    Sent as a dedicated ``type='debug'`` SSE event **only when**
    ``Settings.debug_enabled`` is true. In production the field is
    ``None`` everywhere and no ``debug`` event is emitted on the wire,
    so the full system prompt + RAG context + user-attached file
    contents never leave the backend.

    The shape mirrors what the LLM provider actually receives so the
    dev-mode chat modal can show the developer exactly what the model
    saw — including the system prompt, the (possibly compressed)
    history, the RAG context, and the final user turn. ``model`` is the
    resolved model name (override or settings default).
    """

    model: str
    messages: list[dict[str, str]] = Field(default_factory=list)
    temperature: float | None = None
    max_tokens: int | None = None


class ChatChunk(BaseModel):
    """A streamed piece of the assistant response.

    Reasoning models (DeepSeek, QwQ, o1-style, etc.) expose two parallel
    text streams: the visible response in ``content`` and the internal
    chain-of-thought in ``reasoning``. The frontend can choose to render
    the latter in a collapsible panel; we keep them separate here so the
    UI can do that without re-parsing the content stream.

    ``usage`` is populated on the terminal chunk by the LLM stream (see
    ``LLMChunk.usage``); the route forwards it as a separate SSE event
    of type ``usage`` so the dev-mode chat modal can show token counts
    without disturbing the content/reasoning channels. ``None`` on every
    non-terminal chunk, and ``None`` for the whole stream when the
    provider omits usage.

    ``debug`` carries the full LLM request payload (system prompt +
    history + user turn + model + sampling params) when the dev-mode
    debug modal is enabled. The route emits a single ``type='debug'``
    SSE event on the first chunk that carries this field, then never
    again. ``None`` when ``Settings.debug_enabled`` is false.
    """

    content: str = ""
    reasoning: str | None = None
    usage: dict[str, int] | None = None
    debug: LLMDebugInfo | None = None


class ConversationSummary(BaseModel):
    content: str


class ConversationRequest(BaseModel):
    """Framework-independent request passed to an orchestrator adapter."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    thread_id: int
    bot_id: int
    user_input: str
    bot_name: str
    bot_personality: str
    bot_scenario: str
    first_message: str
    bot_type: str = "rp"
    user_persona: UserPersonaDTO | None = None
    history: list[MessageDTO]
    untrusted_context: list[str]
    context_compressed: bool = False  # True when old messages use short_content
    max_tokens: int | None = None  # Override max tokens
    # V1/V2/V3 character card `mes_example` field — few-shot dialogue
    # examples. Empty string means "do not inject any examples".
    mes_example: str = ""
    temperature: float | None = None  # Override temperature
    uploaded_files: list[ThreadFileDTO] = Field(default_factory=list)


# ── File Upload DTO ─────────────────────────────────────────────────


class ThreadFileDTO(BaseModel):
    id: int
    thread_id: int
    message_id: int | None = None
    filename: str
    file_type: str
    storage_path: str
    extracted_text: str | None = None
    created_at: datetime | None = None


# ── User Personas ───────────────────────────────────────────────────


class UserPersonaDTO(BaseModel):
    id: int
    name: str
    avatar_path: str | None = None
    description: str = ""


class CreatePersonaCommand(BaseModel):
    name: str = Field(min_length=1)
    description: str = ""
    avatar_path: str | None = None


class UpdatePersonaCommand(BaseModel):
    persona_id: int | None = None
    name: str = Field(min_length=1)
    description: str = ""
    avatar_path: str | None = None


# ── Chat Import / Export ───────────────────────────────────────────────


class ExportMessageDTO(BaseModel):
    """Single message for export/import format."""

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    short_content: str | None = None
    created_at: str | None = None


class ImportChatResponse(BaseModel):
    thread_id: int
    message_count: int


# ── Bot versioning ───────────────────────────────────────────────────


class BotVersionDTO(BaseModel):
    """API response model for a single bot version.

    ``snapshot`` is populated only by ``GET /versions/{id}`` (single
    fetch) — list responses keep it as ``None`` to avoid shipping the
    full JSON dump for every row in the timeline.
    """

    id: int
    bot_id: int
    version_number: int
    note: str = ""
    source: Literal["manual", "auto"] = "manual"
    created_at: datetime
    snapshot: dict[str, object] | None = None
