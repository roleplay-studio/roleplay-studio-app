"""m20 — structured logging configuration.

Wraps the stdlib ``logging`` module with a structlog processor
chain so operators can flip between human-readable lines and
JSON output via ``Settings.log_format``:

* ``"pretty"`` (default) — coloured lines for dev, plain for
  CI. Format:
  ``2026-06-12 14:23:11 [info] chat.start thread_id=42``

* ``"json"`` — single-line JSON per event, ideal for ELK /
  Datadog / Loki / CloudWatch ingestion. Format:
  ``{"event": "chat.start", "timestamp": "...", "level": "info",
  "thread_id": 42, ...}``

The two formats are designed to be drop-in compatible with
existing ``logger.info("foo bar=%s", val)`` calls — both stdlib
``logger`` and structlog ``get_logger()`` produce output through
the same ``ProcessorFormatter`` instance. Code can mix them
freely.

A note on the migration: callers don't have to switch from
``logging.getLogger(__name__)`` to ``structlog.get_logger(__name__)``
to get JSON output. The ``structlog.stdlib.ProcessorFormatter``
handles stdlib log records (from uvicorn, alembic, sqlalchemy,
etc.) through the same processor chain. So the existing 200+
``logger.info(…)`` calls keep working unchanged — they just get
JSON-shaped in JSON mode.

Usage from entry points::

    from app.infrastructure.logging import configure_logging
    configure_logging(Settings.from_env())

Usage from tests (to keep test output compact)::

    configure_logging(Settings(_env_file=None, log_format="pretty"))
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import structlog

# ── Shared processor chain ─────────────────────────────────────────
# Order matters: each processor transforms the event_dict before
# the next runs. The chain ends at the renderer (chosen per
# format below) which produces the final string.
#
# Note: ``format_exc_info`` and ``StackInfoRenderer`` must run
# *before* the renderer so exc_info gets formatted into the
# event_dict (or, in JSON mode, dumped as a string field).
_PROCESSORS: list[Any] = [
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.StackInfoRenderer(),
    structlog.processors.format_exc_info,
]


def _build_renderer(fmt: str) -> Any:
    """Return the final processor that converts the event_dict
    to a string. ``fmt`` is case-insensitive."""
    fmt_normalised = fmt.lower()
    if fmt_normalised == "json":
        return structlog.processors.JSONRenderer()
    if fmt_normalised == "pretty":
        return structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    # Fallback — operators sometimes typo. Better to be loud than
    # silently produce an unexpected format.
    raise ValueError(f"unknown log_format={fmt!r}; expected 'pretty' or 'json'")


def configure_logging(settings: Any) -> None:
    """Configure the root logger and structlog to honour
    ``settings.log_level`` + ``settings.log_format``.

    Idempotent — calling twice in a process (e.g. test fixtures
    + entry point) is safe; structlog resets the chain and the
    existing root handler is replaced (not duplicated) so
    output never doubles up.
    """
    level_name = getattr(settings, "log_level", "INFO").upper()
    fmt = getattr(settings, "log_format", "pretty")
    renderer = _build_renderer(fmt)
    level_value = logging.getLevelName(level_name)
    if not isinstance(level_value, int):
        raise ValueError(f"unknown log_level={level_name!r}")

    # 1) Configure structlog. The structlog chain ends with
    #    ``wrap_for_formatter`` — a built-in structlog processor
    #    that converts the event_dict into a (msg, args) pair
    #    consumable by the stdlib Logger.info(msg, *args) API.
    #    The actual rendering (JSON / pretty) happens later, in
    #    the ProcessorFormatter, so structlog and stdlib records
    #    flow through the *same* renderer. Putting the renderer
    #    in structlog's own chain would double-render: structlog
    #    would JSON-encode the event_dict (becomes LogRecord.msg),
    #    then ProcessorFormatter would JSON-encode the already-
    #    encoded string again, producing nested garbage like
    #    ``"event": "{\"x\": 1, ...}"``.
    structlog.configure(
        processors=[*_PROCESSORS, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        wrapper_class=structlog.make_filtering_bound_logger(level_value),
        # Must use the stdlib LoggerFactory, not the default
        # PrintLoggerFactory. PrintLoggerFactory writes
        # directly to ``sys.stdout`` and bypasses our
        # ProcessorFormatter — the JSON would land on stdout
        # while stdlib loggers (uvicorn, alembic) land on stderr
        # (because the root handler is a ``StreamHandler(stderr)``),
        # splitting the log output across two streams. Routing
        # structlog calls through the stdlib root logger
        # guarantees a single ProcessorFormatter instance
        # renders both structlog and stdlib records.
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # 2) Wire the stdlib root logger through the same chain via
    #    ProcessorFormatter. This is what unifies structlog calls
    #    (log.info("event", k=v)) and stdlib calls
    #    (logger.info("event k=%s", v)) into a single output.
    #
    #    ``foreign_pre_chain`` runs on stdlib log records BEFORE
    #    the per-record processors. It must NOT include the
    #    renderer (JSON/Console) — only the metadata enrichers
    #    (level, timestamp, exc_info). The renderer is the
    #    final processor in the chain below, applied to BOTH
    #    structlog and stdlib records so they render identically.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=_PROCESSORS,
        processors=[
            # Remove the stdlib record metadata that structlog
            # already injected via the processors. Without this
            # the JSON output would have both ``level`` (from
            # structlog) and ``levelname`` (from stdlib).
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    # Replace (not append) the root logger's handlers so a
    # second call to configure_logging doesn't double the output.
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)

    # Stream handler — stderr by default so journalctl / docker logs
    # pick it up without redirect magic. Tauri captures this from
    # run_backend.py's child-process pipe.
    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)

    # Optional file sink. Useful for "send me the logs when this
    # crashes" support flows: set ``LOG_FILE=backend.log`` in .env
    # and the next backend restart writes every event to
    # ``$ROLEPLAY_DATA_DIR/backend.log`` (rotated, see below).
    log_file = getattr(settings, "log_file", None)
    if log_file:
        try:
            from logging.handlers import RotatingFileHandler

            # ``log_file`` may be relative to the data dir (so
            # ``logs/backend.log`` works out of the box from
            # Makefile-driven dev runs) or absolute. We resolve it
            # against ``settings.data_dir`` (the canonical data-dir
            # property that honours ``ROLEPLAY_DATA_DIR``) — NOT
            # ``effective_db_path.parent``, which is the parent of
            # the db file and may sit one level deeper when the db
            # lives in a ``demo/`` subfolder (see ``db_path`` in
            # ``.env.example``).
            data_dir = settings.data_dir
            log_path = (
                Path(log_file).expanduser()
                if Path(log_file).expanduser().is_absolute()
                else Path(data_dir) / log_file
            )
            log_path.parent.mkdir(parents=True, exist_ok=True)
            # 10 MB x 3 = 30 MB ceiling. A single chat stream can
            # log hundreds of debug chunks; without rotation this
            # would fill the user's disk on a misbehaving run.
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=10 * 1024 * 1024,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except Exception as exc:  # pragma: no cover — operator-facing
            # Don't crash the backend on a bad log path; surface it
            # on stderr so the operator sees it.
            sys.stderr.write(f"[logging] failed to attach log_file={log_file!r}: {exc}\n")

    root.setLevel(level_value)


def get_logger(name: str | None = None) -> Any:
    """Return a structlog logger. New code should prefer this over
    ``logging.getLogger(name)`` so the key/value API is available
    (``log.info("chat.start", thread_id=42)`` instead of
    ``log.info("chat.start thread=%d", 42)``).

    Existing code using ``logging.getLogger(__name__)`` keeps
    working unchanged because ``configure_logging`` wires the
    stdlib root logger through the same ``ProcessorFormatter``.
    """
    return structlog.get_logger(name)
