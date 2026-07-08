"""m20 unit tests — ``app.infrastructure.logging`` configuration.

Covers the fix for m20 (docs/review.md): the previous code used
``logging.basicConfig`` which produces plain-text lines only.
Operators running behind an aggregator (ELK, Datadog, Loki,
CloudWatch) need either JSON output or a strict format that the
aggregator can parse via regex.

The fix: ``configure_logging(settings)`` in
``app/infrastructure/logging.py`` wires the stdlib root logger
through a structlog processor chain, switchable via
``Settings.log_format`` (``pretty`` or ``json``).

These tests don't assert the *output* of the logger — that's
tricky in pytest (handlers are process-wide and noisy in
parallel). Instead they assert the *configuration* properties
(structlog processors list, log level applied to root logger,
JSON renderer selected when format='json').
"""

from __future__ import annotations

import json
import logging

from app.infrastructure.config import Settings
from app.infrastructure.logging import configure_logging, get_logger


def test_configure_logging_pretty_default(capfd):
    """Default ``log_format="pretty"`` uses the ConsoleRenderer
    which writes to stderr. The output is a free-form
    human-readable line, not JSON — we just assert the event
    name appears somewhere in the captured stream."""
    settings = Settings(_env_file=None)
    assert settings.log_format == "pretty"  # default
    configure_logging(settings)
    log = get_logger("m20.test.pretty")
    log.info("hello.world", key="value")
    captured = capfd.readouterr()
    # ConsoleRenderer writes a coloured string containing the
    # event name. The exact format depends on terminal width
    # and colour autodetect, so we don't assert on the
    # surrounding decoration — just the event-name presence.
    assert "hello.world" in captured.err


def test_configure_logging_json_emits_valid_json(capfd):
    """When ``log_format="json"`` every log line must be valid
    JSON. We use ``capfd`` (fd-level) rather than ``capsys``
    (Python-level) because structlog's ``ConsoleRenderer`` and
    ``JSONRenderer`` write to ``sys.stderr`` by direct reference;
    Python-level capture misses writes that happened through a
    ``sys.stderr`` reference captured at handler-construction
    time."""
    import sys

    settings = Settings(_env_file=None, log_format="json", log_level="INFO")
    configure_logging(settings)
    log = get_logger("m20.test.json")
    # Flush directly to sys.stderr so pytest's capture sees it
    # even if the handler is hooked on a cached reference.
    sys.stderr.flush()
    log.info("event.name", thread_id=42, kind="test")
    sys.stderr.flush()
    captured = capfd.readouterr()
    # JSON output goes to stderr.
    non_empty = [line for line in captured.err.splitlines() if line.strip().startswith("{")]
    assert non_empty, f"expected at least one JSON log line, got: {captured.err!r}"
    last = json.loads(non_empty[-1])
    assert last["event"] == "event.name"
    # kwargs become JSON fields.
    assert last["thread_id"] == 42
    assert last["kind"] == "test"
    assert "level" in last
    assert "timestamp" in last


def test_log_level_propagates_to_root_logger():
    """``Settings.log_level="DEBUG"`` must lower the root logger's
    level so DEBUG-level messages from uvicorn, sqlalchemy, etc.
    become visible. The previous basicConfig only set the root
    level on the first call."""
    settings = Settings(_env_file=None, log_level="DEBUG")
    configure_logging(settings)
    assert logging.getLogger().level == logging.DEBUG
    # And the reverse: a higher level should restrict.
    configure_logging(Settings(_env_file=None, log_level="ERROR"))
    assert logging.getLogger().level == logging.ERROR


def test_configure_logging_is_idempotent():
    """Calling configure_logging twice must not raise and must
    keep the most-recent settings. This matters for tests that
    re-configure per-fixture."""
    s1 = Settings(_env_file=None, log_format="json", log_level="WARNING")
    s2 = Settings(_env_file=None, log_format="pretty", log_level="DEBUG")
    configure_logging(s1)
    configure_logging(s2)
    # The most recent call wins.
    assert logging.getLogger().level == logging.DEBUG


def test_get_logger_returns_structlog_logger():
    """``get_logger(name)`` returns a structlog BoundLogger. We
    don't enforce the exact subclass (structlog has several
    binding wrappers) but the returned object must support the
    key/value API (``log.info("event", key=val)``)."""
    log = get_logger("m20.test.api")
    # If this doesn't raise, the API contract holds.
    log.info("event", x=1)
    log.warning("warn.event", y="two")


def test_existing_stdlib_logger_still_emits_through_structlog(capfd):
    """The compatibility promise from the module docstring:
    callers using ``logging.getLogger(__name__)`` should keep
    working unchanged in either pretty or json mode. We assert
    that a stdlib logger.info call lands on the same handler
    chain as a structlog call. Uses ``capfd`` for the same
    reason as the JSON test above."""
    configure_logging(Settings(_env_file=None, log_format="json", log_level="INFO"))
    stdlib_log = logging.getLogger("m20.test.stdlib")
    stdlib_log.info("stdlib.event")
    captured = capfd.readouterr()
    non_empty = [line for line in captured.err.splitlines() if line.strip().startswith("{")]
    assert non_empty, f"stdlib log line did not reach the handler: {captured.err!r}"
    last = json.loads(non_empty[-1])
    assert last["event"] == "stdlib.event"


def test_log_file_creates_rotating_handler(tmp_path):
    """``Settings.log_file`` must add a ``RotatingFileHandler`` so
    operators can point at a file when reproducing a bug. The handler
    must use the same ``ProcessorFormatter`` as the stderr stream
    handler so JSON in == JSON out (mixed formats would make log
    search impossible)."""
    log_path = tmp_path / "backend.log"
    settings = Settings(
        _env_file=None, log_format="json", log_level="DEBUG", log_file=str(log_path)
    )
    configure_logging(settings)
    log = get_logger("m20.test.file")
    log.info("event.to.file", x=1)
    # Force handlers to flush before we read the file.
    for h in logging.getLogger().handlers:
        h.flush()
    assert log_path.exists(), "log_file was not created"
    text = log_path.read_text(encoding="utf-8")
    assert "event.to.file" in text
    # File must be parseable JSON when log_format=json — that's the
    # whole point of the file sink (machine-parseable for ELK).
    line = next(line for line in text.splitlines() if line.strip().startswith("{"))
    parsed = json.loads(line)
    assert parsed["event"] == "event.to.file"
    assert parsed["x"] == 1


def test_log_file_relative_path_resolves_against_data_dir(tmp_path, monkeypatch):
    """A relative ``log_file`` value must be resolved against
    ``$ROLEPLAY_DATA_DIR`` so an operator can write ``LOG_FILE=logs/backend.log``
    in ``.env`` without thinking about cwd. We point ROLEPLAY_DATA_DIR
    at a tmp dir and assert the file lands inside it."""
    log_file_rel = "logs/backend.log"
    # ROLEPLAY_DATA_DIR is read by Settings.from_env() at access
    # time, so monkeypatching the env before configure_logging is
    # enough — no need to mock Settings itself.
    monkeypatch.setenv("ROLEPLAY_DATA_DIR", str(tmp_path))
    settings = Settings(_env_file=None, log_file=log_file_rel)
    configure_logging(settings)
    log = get_logger("m20.test.relpath")
    log.info("event.relpath")
    for h in logging.getLogger().handlers:
        h.flush()
    expected = tmp_path / "logs" / "backend.log"
    assert expected.exists(), f"relative log_file did not land in data dir; expected {expected}"
    assert "event.relpath" in expected.read_text(encoding="utf-8")
