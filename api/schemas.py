"""Shared API request/response schemas (Pydantic models)."""

from pydantic import BaseModel, Field

from app.domain.enums import BotType


class UpdateConfigRequest(BaseModel):
    temperature: float | None = None
    max_tokens: int | None = None
    embedding_model: str | None = None
    embedding_base_url: str | None = None  # NEW
    embedding_api_key: str | None = None  # NEW; None = unset, "" = explicit no-auth
    fast_model: str | None = None
    knowledge_relevance_threshold: float | None = None
    language: str | None = None
    theme: str | None = None
    summarize_enabled: bool | None = None
    summarize_max_tokens: int | None = None
    summarize_min_length: int | None = None
    thread_summary_enabled: bool | None = None
    thread_summary_interval: int | None = None
    context_compression_enabled: bool | None = None
    context_compression_threshold: int | None = None
    context_compression_keep_recent: int | None = None
    # Cap on messages loaded from the DB for the LLM context.
    # ``None`` leaves the existing value alone so the Settings page
    # can omit it from its PATCH (saves don't overwrite fields the
    # user didn't change). ``Field(ge=10)`` mirrors Settings.
    history_limit: int | None = Field(default=None, ge=10)


class UpdateBotRequest(BaseModel):
    name: str = Field(min_length=1)
    personality: str = Field(min_length=1)
    first_message: str = ""
    scenario: str = ""
    description: str = ""
    avatar_path: str | None = None
    categories: list[str] = Field(default_factory=list)
    bot_type: BotType = BotType.RP
    alternate_greetings: list[str] = Field(default_factory=list)
    mes_example: str | None = None
    dynamic_system_prompt: str = ""
    world_state_prompt: str = ""


class ChatRequest(BaseModel):
    bot_id: int
    user_input: str = Field(min_length=1)
    persona_id: int | None = None
    file_ids: list[int] = Field(default_factory=list)


class KnowledgeRequest(BaseModel):
    content: str = Field(min_length=1)


class EditMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class ConfigureRequest(BaseModel):
    provider: str = "openrouter"
    base_url: str = ""
    api_key: str = ""
    chat_model: str = ""


class RegenerateRequest(BaseModel):
    bot_id: int
    persona_id: int | None = None


class RegenerateStateRequest(BaseModel):
    """Body for the manual state-regeneration endpoint.

    The assistant message id is enough — the orchestrator looks up the
    parent thread, the previous assistant message (for the prior state),
    and the bot (for ``world_state_prompt``).
    """

    assistant_message_id: int


# ── Bot Export / Import ──────────────────────────────────────────────────


class BotExportData(BaseModel):
    """Portable bot export format — JSON dump of a bot's editable fields."""

    name: str
    description: str = ""
    avatar: str = ""
    personality: str
    first_message: str = ""
    scenario: str = ""
    categories: list[str] = Field(default_factory=list)
    bot_type: str = "rp"
    # Round-tripped through export/import so a bot created on machine
    # A keeps its floating prompt and state-gen schema on machine B.
    # Empty string = feature not used by this bot (default).
    dynamic_system_prompt: str = ""
    world_state_prompt: str = ""


class ImportBotRequest(BaseModel):
    """Portable bot import format — name + personality are required."""

    name: str = Field(min_length=1)
    personality: str = Field(min_length=1)
    first_message: str = ""
    scenario: str = ""
    description: str = ""
    avatar: str | None = None
    categories: list[str] = Field(default_factory=list)
    bot_type: str = "rp"
    knowledge: list[str] | None = None
    dynamic_system_prompt: str = ""
    world_state_prompt: str = ""


# ── Settings / Categories ─────────────────────────────────────────


class CategoryAddRequest(BaseModel):
    """Add a new category to the user-managed list."""

    name: str = Field(min_length=1)


class CategoryRenameRequest(BaseModel):
    """Rename a category in place (preserves order, matches by old name)."""

    old_name: str = Field(min_length=1)
    new_name: str = Field(min_length=1)


class CategoryReplaceRequest(BaseModel):
    """Replace the whole category list atomically (used by drag-reorder).

    Validated by ``SettingsService.replace_all`` — duplicates and
    empty entries raise ``ValidationError`` which the global handler
    maps to 400.
    """

    categories: list[str] = Field(default_factory=list)
