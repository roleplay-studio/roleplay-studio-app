"""Composition root for presentation adapters."""

import logging
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
    SettingsService,
    SkillService,
    SummaryService,
    ThreadService,
    TTSService,
    UploadService,
)
from app.infrastructure.config import Settings
from app.infrastructure.format_standart_rp_repairer import FormatStandartRpRepairer
from app.infrastructure.llm.factory import make_llm
from app.infrastructure.orchestration.langgraph_orchestrator import (
    LangGraphConversationOrchestrator,
)
from app.infrastructure.reindex import ReindexService
from app.infrastructure.repositories.sqlalchemy import (
    SqlAlchemyBotRepository,
    SqlAlchemyBotVersionRepository,
    SqlAlchemyMessageRepository,
    SqlAlchemyPersonaRepository,
    SqlAlchemySettingsRepository,
    SqlAlchemyStore,
    SqlAlchemyThreadFileRepository,
    SqlAlchemyThreadRepository,
)
from app.infrastructure.tts import MiniMaxTTSProvider, MockTTSProvider
from app.infrastructure.vectorstore import AsyncChromaKnowledgeBase, ChromaKnowledgeBase

logger = logging.getLogger(__name__)


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
    settings_repo = SqlAlchemySettingsRepository(store)
    settings_svc = SettingsService(settings_repo)
    # Skills — global library + per-bot subscription service. Shares
    # the same SqlAlchemy store as the rest of the app (no separate
    # connection pool — one engine per app, see SqlAlchemyStore).
    skill_svc = SkillService(store=store, settings=settings)

    # LLM — created but NOT yet started. ``startup()`` opens the
    # httpx client; the FastAPI lifespan handler in api/main.py calls
    # ``startup_llms(container)`` and ``shutdown_llms(container)`` so the
    # sockets have a clean owner and an explicit close. This replaces
    # the previous ``__del__``-based cleanup (K2 in docs/review.md).
    #
    # Phase-3 factory dispatch: ``Settings.llm_provider`` selects the
    # implementation. ``"mock"`` swaps in ``MockLLM`` for E2E / CI where
    # hitting a remote LLM is too expensive (rate-limit + cost) for a
    # test suite that only cares about the wire shape, not the prose.
    # Any other provider id (openrouter, openai, lm-studio, deepseek,
    # gigachat, grok, kimi, minimax, yandexgpt, z-ai) routes through
    # the registry-driven ``ProviderLLM`` machinery and reads the
    # per-provider ``default_base_url`` / ``default_model`` from
    # ``api.constants.PROVIDERS``. All paths share the same
    # ``startup()`` / ``close()`` / ``generate_response*`` contract so
    # downstream services need no branching.
    try:
        # ``chat_model`` carries the user-picked model from
        # SetupWizard / Settings. Without this override the factory
        # falls back to the catalog's ``default_model``
        # (``deepseek-chat`` for the deepseek provider), so a user
        # who typed ``deepseek-v4-pro`` into the Settings field
        # silently got ``deepseek-chat`` answers on the next
        # request. Same reasoning as ``fast_model`` further down —
        # both names live in ``Settings``, both need to flow into
        # ``make_llm`` explicitly.
        llm = make_llm(settings, model_override=settings.chat_model)
        fast_llm = make_llm(settings, model_override=settings.fast_model)
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

    # TTS — opt-in: ``disabled`` (default) means no service at all,
    # ``mock`` swaps in the in-process simulator, ``minimax`` hits
    # the real T2A endpoint. Provider construction only happens on
    # the active branches so a misconfigured key doesn't kill the
    # chat pipeline (mirrors the chat LLM behaviour above).
    tts_service: TTSService | None = None
    if settings.tts_provider == "minimax":
        try:
            tts_provider = MiniMaxTTSProvider(settings=settings)
        except ValueError:
            logger.warning(
                "TTS_PROVIDER=minimax but no TTS_API_KEY or LLM_API_KEY set; TTS will be disabled"
            )
            tts_provider = None
        if tts_provider is not None:
            tts_service = TTSService(
                provider=tts_provider,
                cache_dir=settings.effective_tts_cache_dir,
                default_voice=settings.tts_voice_id,
                default_model=settings.tts_model,
            )
    elif settings.tts_provider == "mock":
        mock_provider = MockTTSProvider(settings=settings)
        tts_service = TTSService(
            provider=mock_provider,
            cache_dir=settings.effective_tts_cache_dir,
            default_voice=settings.tts_voice_id,
            default_model=settings.tts_model,
        )

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
            # Phase 4 / Task 12: wire the global SkillService so
            # ``_build_request`` can resolve Bot.skill_ids → SkillDTO
            # for the orchestrator's <Skills> catalog. Same instance
            # the /api/skills routes use — single source of truth.
            skill_service=skill_svc,
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
        settings=settings_svc,
        tts=tts_service,
        skills=skill_svc,
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
    # TTS provider follows the same startup lifecycle so its httpx
    # client is owned by the lifespan handler (no leak on shutdown).
    # ``getattr`` because the lifespan hook only needs the methods
    # when the provider actually has an httpx client to manage
    # (the Mock provider's startup/close are no-ops).
    if container.tts is not None:
        startup = getattr(container.tts.provider, "startup", None)
        if startup is not None:
            await startup()


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
    # Mirror startup: close the TTS provider if one was wired in.
    if container.tts is not None:
        close = getattr(container.tts.provider, "close", None)
        if close is not None:
            try:
                await close()
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
    """Drop cached application services so the next request uses fresh settings.

    .. deprecated::
        This sync helper only clears the cache. After dropping the
        container, the LLM clients inside it must be re-``startup()``-ed
        for chat requests to work — otherwise every LLM raises
        ``RuntimeError: client is not initialised`` on the next call.
        Use :func:`reset_and_start_container` from async code paths
        (the two ``api/routes/config.py`` and ``api/routes/setup.py``
        routes that call this are the original sites that hit the
        bug). Kept for any future sync caller that doesn't need the
        LLM to be live afterwards (e.g. a test fixture).
    """
    get_container.cache_clear()


async def reset_and_start_container() -> None:
    """Drop the cached container, build a fresh one, and re-``startup()``
    its LLM clients. Pair with :func:`shutdown_llms` for the old
    container so the previous httpx sockets are closed cleanly.

    Why this exists
    ---------------
    ``api/main.py::lifespan`` opens the LLM clients **once at process
    boot** via :func:`startup_llms`. Settings-save and wizard-configure
    endpoints call :func:`reset_container` to pick up new ``.env`` /
    ``os.environ`` values, but the old sync helper only clears the
    ``@lru_cache`` — it does NOT call ``startup_llms`` for the new
    container. After saving Settings, the user could no longer send
    chat messages because the new ``BaseOpenAICompatibleLLM`` had
    ``_async_client = None`` and raised on the first request.

    This async helper closes the old LLM clients, drops the cache,
    and starts the new LLM clients in one shot. Idempotent: callable
    multiple times in a row and callable when the cache is empty
    (e.g. in a unit test that doesn't go through the lifespan).
    """
    # 1. If the cache currently holds a container, shut its LLM
    # clients down. ``shutdown_llms`` is best-effort (it swallows
    # close() errors), so a transient socket error here cannot
    # block the new container from being built.
    try:
        current = get_container()
    except Exception:
        current = None
    if current is not None:
        try:
            await shutdown_llms(current)
        except Exception:
            # Belt-and-braces: shutdown_llms already swallows
            # close() errors per-LLM, but if anything else raises
            # (e.g. attribute lookup) we still want to drop the
            # cache and rebuild.
            pass

    # 2. Drop the cache.
    get_container.cache_clear()

    # 3. Rebuild through the lru_cache so the very next
    # ``get_container()`` call returns the SAME instance whose
    # LLM we just started. Without this, the chat handler would
    # call ``get_container()`` → ``build_container()`` → a fresh
    # container with an un-started LLM, the very bug we're fixing.
    # We can't assign to the lru_cache directly (no public API), so
    # we build once here and call get_container() once — the second
    # build is cheap (just object construction, no I/O).
    build_container()  # kept so any external import that pre-warms
    cached = get_container()  # this rebuilds AND memoises
    await startup_llms(cached)
