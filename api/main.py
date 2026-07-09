"""FastAPI application entrypoint."""

import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from api.routes import bots, chat, config, files, knowledge, personas, server_info, setup, threads
from app.application.exceptions import (
    ApplicationError,
    ExternalServiceError,
    NotFoundError,
    UploadError,
    ValidationError,
)
from app.bootstrap import get_container

logger = logging.getLogger(__name__)


async def _access_log_dispatch(request: Request, call_next):
    """HTTP access log.

    Logs every request with method, path, status, and elapsed
    ms. Skips the noisy ``/api/health`` probe by default — set
    ``LOG_HEALTH=1`` in the environment to re-enable. The
    middleware emits at INFO for 2xx/3xx and at WARNING for
    4xx/5xx so the ``make logs-errors`` surface stays useful.
    ``X-Forwarded-For`` is intentionally ignored — this is a
    desktop Tauri app and the only client is local.

    Implemented as a top-level coroutine + ``add_middleware``
    rather than the ``@app.middleware("http")`` decorator
    because the decorator variant has subtle pytest
    capture-logger interaction issues that were a 30-minute
    rabbit hole to debug. The explicit ``BaseHTTPMiddleware``
    registration is more verbose but the logger behaviour
    matches the production entry point (``run_backend.py``)
    exactly.
    """
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    path = request.url.path
    if path == "/api/health" and not os.getenv("LOG_HEALTH"):
        return response
    status_code = response.status_code
    line = (
        f"{request.method} {path} -> {status_code} "
        f"({elapsed_ms:.1f}ms)"
    )
    if status_code >= 500:
        logger.error(line)
    elif status_code >= 400:
        logger.warning(line)
    else:
        logger.info(line)
    return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize the database and the LLM clients on startup.

    The LLM clients (httpx.AsyncClient instances) are now opened in
    startup and closed in shutdown — see K1+K2 in docs/review.md.
    Previously they were created lazily and cleaned up via
    ``__del__``-based hacks that could race with the event loop.
    """
    logger.info("Initializing database...")
    from app.infrastructure.config import Settings
    from app.infrastructure.repositories.sqlalchemy import SqlAlchemyStore

    store = SqlAlchemyStore(settings=Settings.from_env())
    await store.init_db()
    logger.info("Database initialized.")

    # Warm up container cache, then open the LLM clients.
    container = get_container()
    from app.bootstrap import shutdown_llms, startup_llms

    await startup_llms(container)
    logger.info("LLM clients started.")
    try:
        yield
    finally:
        await shutdown_llms(container)
        logger.info("LLM clients closed.")
        logger.info("Shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Roleplay Studio API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        debug=True,
        lifespan=lifespan,
    )

    # M-review2: ``allow_credentials=True`` with ``allow_origins=["*"]``
    # is rejected by every CORS-aware browser (see fetch spec) and was a
    # no-op even before. This is a desktop Tauri app — the SPA carries
    # no cookies and the API is not a public web service, so dropping
    # credentials is the safe default. ``["*"]`` origins stay because
    # we don't want to enumerate every Tauri/WebView origin a user
    # might install this through.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Access log middleware ───────────────────────────────────
    # ``add_middleware(BaseHTTPMiddleware, dispatch=...)`` is the
    # explicit form of the ``@app.middleware("http")`` decorator.
    # We use the explicit form so the test fixture can
    # ``assert_called`` on the dispatch coroutine, and so the
    # logger context is unambiguous in stack traces.
    app.add_middleware(BaseHTTPMiddleware, dispatch=_access_log_dispatch)

    # ── Static files: uploaded avatars ───────────────────────────
    # The folder that backs the public ``/uploads/...`` URL is
    # controlled by the ``UPLOAD_DIR`` env var (see .env.example).
    # Relative values resolve against ``ROLEPLAY_DATA_DIR`` when set,
    # otherwise the project root — same convention as the rest of
    # Settings paths. ``effective_upload_dir`` is absolute.
    from app.infrastructure.config import Settings

    _settings = Settings.from_env()
    uploads_dir = str(_settings.effective_upload_dir)
    os.makedirs(uploads_dir, exist_ok=True)
    app.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")

    # ── Routers ──────────────────────────────────────────────────
    app.include_router(bots.router, prefix="/api/bots", tags=["Bots"])
    app.include_router(threads.router, prefix="/api/threads", tags=["Threads"])
    app.include_router(chat.router, prefix="/api/threads", tags=["Chat"])
    app.include_router(files.router, prefix="/api/threads", tags=["Files"])
    app.include_router(knowledge.router, prefix="/api/knowledge", tags=["Knowledge"])
    app.include_router(personas.router, prefix="/api/personas", tags=["Personas"])
    app.include_router(config.router, prefix="/api/config", tags=["Config"])
    app.include_router(setup.router, prefix="/api/setup", tags=["Setup"])
    app.include_router(server_info.router, tags=["Server Info"])

    @app.get("/api/health")
    async def health():
        """Liveness + DB readiness probe used by the setup wizard.

        Returns 200 with a JSON body when both the HTTP server and the
        configured database are reachable. When the DB round-trip fails
        (locked, missing migrations, broken on-disk file, …) the route
        returns 503 with a human-readable ``db`` field so the front-end
        can show the user a meaningful error instead of an infinite
        loading screen.
        """
        from api.bots_registry import list_starter_bots
        from app.bootstrap import get_container
        from app.infrastructure.config import Settings
        from app.infrastructure.repositories.sqlalchemy import SqlAlchemyStore

        # M-review2: reuse the shared SqlAlchemyStore from the
        # application container instead of constructing a fresh
        # ``SqlAlchemyStore`` (and a fresh engine + connection pool)
        # on every probe. Falls back to a transient instance if the
        # container hasn't been built yet (e.g. very first probe
        # before lifespan has warmed the cache).
        container = get_container()
        store = container.store
        if not isinstance(store, SqlAlchemyStore):
            store = SqlAlchemyStore(settings=Settings.from_env())

        db_status = "ok"
        db_error: str | None = None
        try:
            await store.health_check()
        except Exception as e:
            db_status = "error"
            db_error = f"{type(e).__name__}: {e}"

        try:
            starter_bots_count = len(list_starter_bots())
        except Exception:
            starter_bots_count = 0

        overall = "ok" if db_status == "ok" else "degraded"
        body = {
            "status": overall,
            "db": db_status,
            "db_error": db_error,
            "starter_bots_count": starter_bots_count,
            "version": Settings.from_env().version,
        }
        if db_status != "ok":
            return JSONResponse(body, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
        return body

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Convert unhandled exceptions into JSON so the front-end can
        distinguish "backend down / 5xx" from a network/CORS failure.

        The response carries a stable ``request_id`` for support tickets
        and a generic ``detail`` — the exception type and message are
        logged at ERROR level with the same id, never returned. Returning
        ``f"{type(exc).__name__}: {exc}"`` was a review2.md finding:
        it leaked internal types, file paths, and (occasionally)
        provider secrets back to the client.
        """
        request_id = uuid.uuid4().hex
        logger.exception(
            "Unhandled error on %s %s [request_id=%s]",
            request.method,
            request.url.path,
            request_id,
        )
        return JSONResponse(
            {
                "detail": "Internal server error",
                "request_id": request_id,
            },
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError):
        """Map application-layer exceptions to HTTP responses.

        Application services raise ``ApplicationError`` subclasses
        (``NotFoundError``, ``ValidationError``, ``UploadError``,
        ``ExternalServiceError``) instead of HTTP-specific exceptions so
        the application layer stays free of ``fastapi`` imports
        (review2.md). This handler is the single point that knows
        how those domain failures map onto HTTP — adding a new
        domain error here is a one-line change with no churn in
        service code or route handlers.

        Logging policy:
          - 404 / 4xx — INFO level with method + path; user-facing
            errors are noise at WARNING. A missing bot on a render
            thread that the user refreshed shouldn't flood logs.
          - 5xx / ExternalServiceError — WARNING. The middleware
            above will also tag the request line as WARNING (the
            ``>= 500`` branch there), so the message ends up
            doubled-on-purpose via two surfaces: the per-request
            summary and the per-error detail. Cheap insurance.
        """
        # NotFoundError is the most specific — match it first.
        if isinstance(exc, NotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, UploadError):
            # UploadError carries its own status (e.g. 413 for too
            # large) so the upload service can distinguish "user did
            # something wrong" from "client lied about Content-Length".
            status_code = exc.http_status
        elif isinstance(exc, ValidationError):
            status_code = exc.http_status
        elif isinstance(exc, ExternalServiceError):
            status_code = status.HTTP_502_BAD_GATEWAY
        else:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        if status_code >= 500:
            logger.warning(
                "ApplicationError on %s %s [%s]: %s",
                request.method,
                request.url.path,
                type(exc).__name__,
                exc,
            )
        elif status_code >= 400 and not isinstance(exc, NotFoundError):
            # 404 is so routine (a tab refresh after the user
            # deleted a bot) that WARNING would flood. Tag it INFO.
            # 4xx that aren't 404 are worth seeing — usually the
            # client is misconfigured or sending bad input.
            logger.info(
                "ApplicationError on %s %s [%s]: %s",
                request.method,
                request.url.path,
                type(exc).__name__,
                exc,
            )

        body: dict = {"detail": str(exc)}
        # UploadError carries a stable ``code`` so the client can
        # branch on it without parsing the human message.
        code = getattr(exc, "code", None)
        if code is not None:
            body["code"] = code
        return JSONResponse(body, status_code=status_code)

    return app


app = create_app()
