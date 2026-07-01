"""Composition root for presentation adapters."""

from functools import lru_cache

from app.application.container import ApplicationContainer
from app.application.exceptions import ConfigurationError
from app.application.services import (
    BotImportService,
    BotService,
    BotVersionService,
    ChatService,
    KnowledgeService,
    MessageSummarizer,
    PersonaService,
    SummaryService,
    ThreadService,
    UploadService,
)
from app.infrastructure.config import Settings
from app.infrastructure.format_standart_rp_repairer import FormatStandartRpRepairer
from app.infrastructure.llm import OpenRouterLLM
from app.infrastructure.orchestration.langgraph_orchestrator import (
    LangGraphConversationOrchestrator,
)
from app.infrastructure.reindex import ReindexService
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyBotRepository,
    SqlAlchemyBotVersionRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyPersonaRepository,
    SqlAlchemyStore,
    SqlAlchemyThreadFileRepository,
    SqlAlchemyThreadRepository,
)
from app.infrastructure.vectorstore import AsyncChromaKnowledgeBase, ChromaKnowledgeBase


def build_container(settings: Settings | None = None) -> ApplicationContainer:
    settings = settings or Settings.from_env()
    store = SqlAlchemyStore(settings=settings)
    # init_db is called separately via lifespan — not here
    bot_repo = SqlAlchemyBotRepository(store)
    thread_repo = SqlAlchemyThreadRepository(store)
    message_repo = SqlAlchemyMessageRepository(store)
    knowledge = AsyncChromaKnowledgeBase(ChromaKnowledgeBase(settings=settings))
    # Scan for stale collections (embedding model changed since last index)
    try:
        sync_kb = ChromaKnowledgeBase(settings=settings)
        stale_bots = sync_kb.scan_for_stale_collections()
    except Exception:
        stale_bots = []
    persona_repo = SqlAlchemyPersonaRepository(store)
    bot_version_repo = SqlAlchemyBotVersionRepository(store)
    bot_version_svc = BotVersionService(bot_version_repo, bot_repo)

    # LLM — created but NOT yet started. ``startup()`` opens the
    # httpx client; the FastAPI lifespan handler in api/main.py calls
    # ``startup_llms(container)`` and ``shutdown_llms(container)`` so the
    # sockets have a clean owner and an explicit close. This replaces
    # the previous ``__del__``-based cleanup (K2 in docs/review.md).
    try:
        llm = OpenRouterLLM(settings=settings)
        fast_llm = OpenRouterLLM(settings=settings, model=settings.fast_model)
    except (ConfigurationError, Exception):
        llm = None
        fast_llm = None

    orchestrator = (
        LangGraphConversationOrchestrator(llm, settings=settings) if llm is not None else None
    )

    # File upload service
    files_repo = SqlAlchemyThreadFileRepository(store)
    upload_svc = UploadService(files_repo, bot_repo, fast_llm or llm, settings) if llm else None

    # Message summarizer — generates short_content and thread summaries
    summarizer = MessageSummarizer(fast_llm or llm, message_repo) if llm else None

    # Markdown repairer — repairs broken markdown in LLM output for
    # RP bots before the response is persisted. Always constructed
    # so the chat service can decide based on bot_type at request
    # time; the actual library call only fires for BotType.RP.
    markdown_repairer = FormatStandartRpRepairer()

    return ApplicationContainer(
        bots=BotService(bot_repo, bot_versions=bot_version_repo),
        threads=ThreadService(thread_repo, message_repo, bots=bot_repo),
        knowledge=KnowledgeService(knowledge),
        personas=PersonaService(persona_repo),
        bot_versions=bot_version_svc,
        chat=ChatService(
            bot_repo,
            message_repo,
            knowledge,
            orchestrator,
            settings=settings,
            personas=persona_repo,
            threads=thread_repo,
            llm=llm,
            files=files_repo,
            summarizer=summarizer,
            markdown_repairer=markdown_repairer,
        )
        if orchestrator
        else None,
        summarizer=summarizer,
        summary=SummaryService(fast_llm or llm) if llm else None,
        upload=upload_svc,
        bot_import=BotImportService(
            bot_repo=bot_repo,
            knowledge_service=KnowledgeService(knowledge),
            avatar_dir=str(settings.avatars_dir),
        ),
        reindex=ReindexService(),
        store=store,
        stale_embedding_bots=frozenset(stale_bots),
        markdown_repairer=markdown_repairer,
    )


async def startup_llms(container: ApplicationContainer) -> None:
    """Open the httpx clients for every OpenRouterLLM in the container.

    Idempotent. Pair with ``shutdown_llms`` from the FastAPI lifespan.
    """
    from app.application.container import ApplicationContainer

    if not isinstance(container, ApplicationContainer):
        return
    llms = [
        c
        for c in (
            container.chat._llm if container.chat else None,
            container.summarizer._llm if container.summarizer else None,
            container.summary._llm if container.summary else None,
        )
        if c is not None
    ]
    # Also catch fast_llm held by the upload service.
    if container.upload is not None and getattr(container.upload, "_llm", None) is not None:
        llms.append(container.upload._llm)
    # The fast_llm is also used directly by ChatService for auto-naming,
    # but the chat service keeps it inside self._llm. The summarizer /
    # summary services keep their own. To avoid missing any, walk
    # every OpenRouterLLM known to the container and dedupe.
    seen: set[int] = set()
    for llm in llms:
        if id(llm) in seen:
            continue
        seen.add(id(llm))
        await llm.startup()


async def shutdown_llms(container: ApplicationContainer) -> None:
    """Close the httpx clients held by OpenRouterLLMs in the container.

    Best-effort: an exception in one close() does not prevent the
    others from running.
    """
    from app.application.container import ApplicationContainer

    if not isinstance(container, ApplicationContainer):
        return
    candidates: list[object] = []
    if container.chat is not None and getattr(container.chat, "_llm", None) is not None:
        candidates.append(container.chat._llm)
    if container.summarizer is not None and getattr(container.summarizer, "_llm", None) is not None:
        candidates.append(container.summarizer._llm)
    if container.summary is not None and getattr(container.summary, "_llm", None) is not None:
        candidates.append(container.summary._llm)
    if container.upload is not None and getattr(container.upload, "_llm", None) is not None:
        candidates.append(container.upload._llm)
    seen: set[int] = set()
    for llm in candidates:
        if id(llm) in seen:
            continue
        seen.add(id(llm))
        try:
            await llm.close()
        except Exception:
            pass


async def init_container(settings: Settings | None = None) -> ApplicationContainer:
    """Build container and initialize the database (async)."""
    settings = settings or Settings.from_env()
    store = SqlAlchemyStore(settings=settings)
    await store.init_db()
    # Return build_container result — it re-creates store, which is fine
    # since SqlAlchemyStore is stateless after init_db
    return build_container(settings)


@lru_cache(maxsize=1)
def get_container() -> ApplicationContainer:
    return build_container()


def reset_container() -> None:
    """Drop cached application services so the next request uses fresh settings."""
    get_container.cache_clear()
