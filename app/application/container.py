"""Application services container."""

from dataclasses import dataclass, field

from app.application.ports import MarkdownRepairer
from app.application.services import (
    BotImportService,
    BotService,
    BotVersionService,
    ChatService,
    KnowledgeService,
    MessageSummarizer,
    PersonaService,
    SettingsService,
    SummaryService,
    ThreadService,
    UploadService,
)
from app.infrastructure.reindex import ReindexService


@dataclass(frozen=True)
class ApplicationContainer:
    bots: BotService
    threads: ThreadService
    knowledge: KnowledgeService
    personas: PersonaService
    bot_versions: BotVersionService | None = None
    chat: ChatService | None = None
    summarizer: MessageSummarizer | None = None
    summary: SummaryService | None = None
    upload: UploadService | None = None
    bot_import: BotImportService | None = None
    reindex: ReindexService = field(default_factory=ReindexService)
    # M-review2: shared SQLAlchemy store so the /api/health probe
    # reuses the engine the repositories already use instead of
    # constructing a fresh one on every probe (engine + connection
    # pool + file descriptor per probe).
    store: object = None
    stale_embedding_bots: frozenset[int] = field(default_factory=frozenset)
    # MarkdownRepairer is injected into ChatService for repairing
    # broken markdown in LLM responses before persisting them.
    # Default is a NullMarkdownRepairer (no-op) so unit tests and
    # setups without the format-standart-rp library still work.
    markdown_repairer: MarkdownRepairer | None = None
    # ``SettingsService`` owns the app-wide configurable lists
    # (today: the bot category catalog). Required for the
    # `/api/bots/categories` CRUD endpoints to work; defaults to
    # ``None`` so existing tests that build the dataclass manually
    # still pass without a settings service.
    settings: SettingsService | None = None
