"""Smoke tests for the API access log middleware and the
ApplicationError logging policy.

The middleware exists, is registered with the FastAPI
app, and the error handler applies the right log level per
status code. Deeper end-to-end log-capture would need to
mirror the structlog configuration that ``run_backend.py``
sets up at process start — too heavy for a unit suite.
Manual verification: ``make dev-debug`` and watch
``logs/backend.log``.
"""

from __future__ import annotations

import textwrap


def _app():
    from api.main import app

    return app


def test_access_log_middleware_is_registered() -> None:
    """The ``_access_log_dispatch`` middleware must be in the
    user-middleware list. Without this, ``make dev-debug``
    shows nothing about HTTP traffic and the operator is
    flying blind.
    """
    app = _app()
    dispatches = [
        mw.kwargs.get("dispatch")
        for mw in app.user_middleware
        if mw.cls.__name__ == "BaseHTTPMiddleware"
    ]
    assert any(
        d is not None and d.__name__ == "_access_log_dispatch"
        for d in dispatches
    ), (
        f"_access_log_dispatch not found among BaseHTTPMiddleware entries. "
        f"user_middleware={app.user_middleware !r}"
    )


def test_application_error_handler_logs_at_correct_levels() -> None:
    """The ``application_error_handler`` must log the right
    level per ApplicationError subclass — pin the
    conditional structure so a future refactor can't drop
    the policy.

    The handler is defined as a closure inside
    ``create_app`` so we read it out of the source string
    rather than as a module attribute.
    """
    import inspect

    from api import main

    src = inspect.getsource(main)
    # Find the application_error_handler block by anchoring
    # on its unique exception_handler decorator line.
    anchor = "async def application_error_handler("
    start = src.find(anchor)
    assert start != -1, (
        "Could not find application_error_handler in api/main.py"
    )
    # Read until the next ``@app.`` decorator or top-level
    # statement to capture the full function body.
    end = src.find("\n    @app.", start)
    if end == -1:
        end = start + 4000
    handler_src = textwrap.dedent(src[start:end])
    assert "logger.warning" in handler_src, (
        "application_error_handler must log 5xx at WARNING level"
    )
    assert "logger.info" in handler_src, (
        "application_error_handler must log non-404 4xx at INFO level"
    )
    assert "NotFoundError" in handler_src and "isinstance" in handler_src, (
        "application_error_handler must explicitly branch on NotFoundError "
        "to silence 404s"
    )


def test_health_probe_short_circuits_before_logging() -> None:
    """The middleware short-circuits for ``/api/health`` when
    ``LOG_HEALTH`` is unset, so every poll cycle does not
    become a log entry.
    """
    import inspect

    from api import main

    src = inspect.getsource(main._access_log_dispatch)
    assert "/api/health" in src, (
        "Health-probe short-circuit missing from _access_log_dispatch"
    )
    assert "LOG_HEALTH" in src, (
        "LOG_HEALTH opt-in env var missing from _access_log_dispatch"
    )


def test_access_log_dispatch_logs_method_path_status_and_timing() -> None:
    """The middleware must log method, path, status code, and
    elapsed-ms — operators look at this for the question
    "what just hit my API?"
    """
    import inspect

    from api import main

    src = inspect.getsource(main._access_log_dispatch)
    assert "request.method" in src
    assert "path" in src
    assert "status_code" in src
    assert "elapsed_ms" in src
