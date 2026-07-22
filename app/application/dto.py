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

from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    # Floating system reminder + world-state prompt. Empty string
    # by default — bots that don't use the feature omit them. The
    # ``from_orm_bot`` factory pulls both from the SQLAlchemy row via
    # ``getattr`` so older bots that predate the columns still
    # deserialise cleanly.
    dynamic_system_prompt: str = ""
    world_state_prompt: str = ""
    # Attached skills (Phase 2 / Task 13). Stored as a JSON list of
    # skill IDs in ``Bot.skill_ids``. The API exposes just the IDs
    # here (slim — no instruction payload); the frontend calls
    # ``GET /api/bots/{id}/skills`` separately when it needs the
    # full SkillDTO list. ``skills_invalid`` lists IDs that no
    # longer resolve to a live GlobalSkill — frontend can offer a
    # "remove orphan" shortcut, mirroring the categories pattern.
    skills: list[int] = Field(default_factory=list)
    skills_invalid: list[int] = Field(default_factory=list)

    @classmethod
    def from_orm_bot(
        cls,
        bot: Bot,
        thread_count: int = 0,
        valid_categories: set[str] | None = None,
        valid_skill_ids: set[int] | None = None,
    ) -> BotResponse:
        """Build an API response from a SQLModel Bot instance.

        ``valid_categories`` is the current user-defined category
        list. When supplied, every entry in ``bot.categories`` is
        cross-referenced and orphaned values land in
        ``categories_invalid`` (raw ``categories`` is left
        unchanged). When ``None`` (e.g. legacy test fixtures),
        ``categories_invalid`` defaults to empty so the existing
        contract is preserved.

        ``valid_skill_ids`` follows the same pattern for the Skills
        feature. When supplied, every entry in ``bot.skill_ids`` is
        cross-referenced against the live GlobalSkill library and
        orphan IDs land in ``skills_invalid``. The raw list goes
        straight into ``skills`` regardless (preserves the on-disk
        history). When ``None``, ``skills_invalid`` is empty.
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

        # Phase 2 / Task 13 — skills projection.
        # Mirrors the categories block above: defensive JSON parse,
        # cross-reference against valid_skill_ids, raw list preserved.
        skill_ids: list[int] = []
        skill_ids_raw = getattr(bot, "skill_ids", "[]") or "[]"
        if isinstance(skill_ids_raw, list):
            skill_ids = [int(i) for i in skill_ids_raw if isinstance(i, (int, float))]
        elif isinstance(skill_ids_raw, str):
            try:
                parsed = json.loads(skill_ids_raw)
                if isinstance(parsed, list):
                    skill_ids = [int(i) for i in parsed if isinstance(i, (int, float))]
            except (json.JSONDecodeError, TypeError):
                skill_ids = []
        skills_invalid: list[int] = []
        if valid_skill_ids is not None and skill_ids:
            skills_invalid = [i for i in skill_ids if i not in valid_skill_ids]

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
            dynamic_system_prompt=getattr(bot, "dynamic_system_prompt", "") or "",
            world_state_prompt=getattr(bot, "world_state_prompt", "") or "",
            skills=skill_ids,
            skills_invalid=skills_invalid,
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
    # Per-message world-state snapshot (opaque string). Populated by
    # the background state-update task after each assistant response;
    # ``None`` for older messages that predate the feature and for
    # messages where the bot has no ``world_state_prompt``. The bot
    # author owns the output format via ``Bot.world_state_prompt`` —
    # we do not parse, validate, or constrain it.
    state: str | None = None
    # Captured at stream time so the chat UI can show what was
    # actually sent to the LLM. Set on assistant messages only when
    # the bot has a non-empty ``dynamic_system_prompt`` (the field is
    # populated by the orchestrator's post-stream refresh path,
    # parallel to how ``reasoning`` is captured today).
    dynamic_system_prompt: str | None = None
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
    # FK to the thread this one was forked from. None for root threads.
    parent_thread_id: int | None = None
    # ── Preview fields populated by list_with_preview / list_recent_threads
    # ── These are denormalised for the thread-list UI; the source of
    # truth remains in the messages and personas tables. None on the
    # legacy /api/bots/{id}/threads endpoint may return None until the
    # call sites are migrated to the enriched method.
    #
    # message_count: total active-chain messages (branch_group IS NULL OR
    #   is_active). Distinct from ThreadStatsDTO which counts the
    #   generation_status='complete' subset; here we count every message
    #   that's still part of the displayed chain.
    message_count: int = 0
    # last_message_at: timestamp of the most recent active message in the
    #   thread. Used by sort-by-last and group-by-bot orderings.
    last_message_at: datetime | None = None
    # last_message_preview: short_content of the most recent
    #   ``role='assistant'`` active message (preferred over ``content`` —
    #   short_content is the Summarizer's compact form). When the
    #   summarizer hasn't run yet, this is null and the UI falls back to
    #   ``summary``.
    last_message_preview: str | None = None
    # last_message_role: 'user' | 'assistant' | 'system' of the most
    #   recent active message. Lets the UI decide icon/avatar without a
    #   second join.
    last_message_role: str | None = None
    # persona_avatar_path: avatar of the persona the bot is talking to.
    #   Same semantics as Persona.avatar_path — null means no avatar
    #   uploaded, NOT "no persona".
    persona_avatar_path: str | None = None


class ThreadStatsDTO(BaseModel):
    """Lightweight snapshot of a thread's size for header stats.

    Returned by ``GET /api/threads/{thread_id}/stats``. Independent of
    pagination — counts the entire active chain (with the same
    ``branch_group IS NULL OR is_active`` filter used by
    ``list_for_thread``) so the chat header shows real numbers rather
    than just the latest page (50 by default).

    ``token_estimate`` is a best-effort ceiling (chars/4 rounded up),
    matching the rough proxy the frontend already uses. Callers should
    treat it as an indicator, not a billing-grade count.
    """

    thread_id: int
    message_count: int
    token_estimate: int


class RecentThreadDTO(BaseModel):
    """A thread with bot info, persona name, and last message preview.

    Used by the cross-bot recent-chats view (Dashboard sidebar +
    Chat.svelte fallback view). Populated by the same enriched
    list_recent_threads SQL as ThreadDTO preview fields; backend-side
    cost is one query (LEFT JOIN + LATERAL subqueries) for the whole
    list.
    """

    thread_id: int
    name: str
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
    # message_count: total active-chain messages (see ThreadDTO field
    # for the exact filter). Distinct from "thread has any messages"
    # — a thread with 200 historical messages and 0 active has
    # message_count=0.
    message_count: int = 0
    # last_message_short_content: short_content of the most recent
    # assistant message. Preferred over last_message_preview when the
    # Summarizer has run, because short_content is structured for the
    # list-row slot. UI precedence: short_content → preview → summary
    # → empty.
    last_message_short_content: str | None = None


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
    dynamic_system_prompt: str = ""
    world_state_prompt: str = ""


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
    # Floating system reminder injected right before the last user turn.
    # Empty string = no floating prompt (default for bots that don't
    # use the feature). Variable substitution (``{{char}}`` /
    # ``{{user}}``) is applied by the orchestrator.
    dynamic_system_prompt: str = ""
    # System prompt for the background state-update task. The bot
    # developer owns the output format. Empty string = skip the
    # background state task entirely.
    world_state_prompt: str = ""
    # World-state snapshot from the previous assistant turn in this
    # thread. The chat service fills this from ``history`` (the
    # most-recent ``assistant`` message's ``state`` column) before
    # handing off to the orchestrator. Empty string when there's
    # no prior assistant turn, the bot hasn't produced a state yet,
    # or state-update was disabled (no ``world_state_prompt``).
    # The orchestrator turns this into a ``system`` message with a
    # ``[World state from previous turn]`` prefix, right after the
    # floating reminder so the LLM sees the freshest world context
    # before the new user turn.
    prev_world_state: str = ""
    # Resolved list of skills attached to this bot. Populated by
    # ``ChatService._build_request`` from ``Bot.skill_ids`` joined
    # against the global ``GlobalSkill`` table. Empty list = no
    # skills (the orchestrator omits the <Skills> block entirely).
    # The orchestrator renders these as a single
    # ``<Skills>...</Skills>`` system message placed right after
    # ``<Persona>/<Scenario>`` so the LLM sees the behavioural
    # rules in a stable position. See spec §7.
    skills: list[SkillDTO] = Field(default_factory=list)


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


# ── Skills (Phase 2) ─────────────────────────────────────────────
#
# DTOs for the Skills feature. See spec §5.1, §5.2, §5.3.
#
# Pattern: ``*Command`` = inbound (POST/PUT body), ``*DTO`` = outbound
# (response shape). ``BotSkillDTO`` is the lightweight projection of
# ``SkillDTO`` used by ``BotResponse.skills`` — NO ``instruction`` to
# keep ``GET /api/bots`` payload small.


class SkillDTO(BaseModel):
    """API response for a single :class:`GlobalSkill`. See spec §5.1.

    Used by:
    - ``GET /api/skills/{id}``
    - ``GET /api/skills`` (list)
    - ``GET /api/bots/{bot_id}/skills`` (resolved list)
    - ``ConversationRequest.skills`` (orchestrator input)
    """

    id: int
    name: str
    description: str
    instruction: str
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateSkillCommand(BaseModel):
    """``POST /api/skills`` body. See spec §5.1.

    Validation:
    - ``name`` — stripped of whitespace; non-empty after trim; ≤64 chars
    - ``description`` — ≤300 chars (optional)
    - ``instruction`` — non-empty; ≤4000 chars (caps prompt cost)
    - ``tags`` — lowercased + stripped + deduped (insertion order kept)
    """

    name: str = Field(min_length=1, max_length=64)
    description: str = Field(default="", max_length=300)
    instruction: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must be non-empty after trim")
        return v

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, v: list[str]) -> list[str]:
        """Lowercase, strip, dedupe. Preserve insertion order.

        Matches :meth:`SqlAlchemySkillRepository._normalise_tags` —
        single source of truth for tag canonicalisation.
        """
        seen: set[str] = set()
        out: list[str] = []
        for t in v:
            t = t.strip().lower()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out


class UpdateSkillCommand(BaseModel):
    """``PUT /api/skills/{id}`` body. All fields optional.

    Only the supplied fields are touched by the service layer; ``None``
    means "leave unchanged" (parity with other Update*Command shapes
    in this module — see ``UpdatePersonaCommand``).
    """

    name: str | None = Field(default=None, min_length=1, max_length=64)
    description: str | None = Field(default=None, max_length=300)
    instruction: str | None = Field(default=None, min_length=1, max_length=4000)
    tags: list[str] | None = None

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not v:
            raise ValueError("name must be non-empty after trim")
        return v

    @field_validator("tags")
    @classmethod
    def _normalize_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        seen: set[str] = set()
        out: list[str] = []
        for t in v:
            t = t.strip().lower()
            if t and t not in seen:
                seen.add(t)
                out.append(t)
        return out


class BotSkillDTO(BaseModel):
    """Lightweight skill projection for ``BotResponse.skills``. See spec §5.3.

    Excludes ``instruction`` (large markdown blob) to keep
    ``GET /api/bots`` payload small. Full content is available via
    ``GET /api/skills/{id}`` for the Library preview modal.

    Includes ``description`` because the chips in the BotEditPage
    Skills section use it as a tooltip on hover.
    """

    id: int
    name: str
    description: str


class UpdateBotSkillsCommand(BaseModel):
    """``PUT /api/bots/{bot_id}/skills`` body. See spec §5.2.

    Replaces the bot's entire skill list (not a delta). Empty list =
    clear all skills.
    """

    skill_ids: list[int] = Field(default_factory=list)


class ConflictErrorResponse(BaseModel):
    """409 response body for skill-deletion conflicts. See spec §6.4.

    Stable shape — the frontend reads ``attached_to`` to render
    "used by N bots" and offers navigation to the affected bots.
    """

    detail: str
    attached_to: list[int] = Field(default_factory=list)
