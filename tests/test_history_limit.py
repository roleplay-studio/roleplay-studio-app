"""Tests for the LLM ``history_limit`` config — the cap on how many
messages are loaded from the DB into the LLM context.

Two scenarios are covered:

1. ``Settings`` defaults to 1000 (raised from 200 so DEBUG1-class
   threads don't silently drop history).
2. ``_load_full_history`` logs a warning when the loaded page hits
   the cap, so operators can see in logs that the user outgrew the
   default and needs to raise it (or is hitting it intentionally).
3. ``UpdateConfigRequest.history_limit`` accepts the new field and
   the route writes ``HISTORY_LIMIT`` into ``.env`` with the same
   validation as Settings (``ge=10``).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

# ── Settings default ───────────────────────────────────────────────


def test_history_limit_default_is_one_thousand() -> None:
    """The default cap is 1000 (raised from 200).

    Verified directly so a future operator who bumps it back down
    to 200 cannot do so without seeing the test fail.
    """
    from app.infrastructure.config import Settings

    s = Settings(_env_file=None)
    assert s.history_limit == 1000


def test_history_limit_minimum_is_ten() -> None:
    """Pydantic ``ge=10`` enforces a floor. Anything lower would
    surprise users in the LLM debug panel where a chat with 11
    messages shows only 10.
    """
    from pydantic import ValidationError

    from app.infrastructure.config import Settings

    with pytest.raises(ValidationError):
        Settings(_env_file=None, history_limit=5)


def test_history_limit_round_trips_via_env(monkeypatch) -> None:
    """``Settings.from_env`` honours ``HISTORY_LIMIT`` so an operator
    who sets it in ``.env`` doesn't need to restart with kwargs.
    """
    from app.infrastructure.config import Settings

    monkeypatch.setenv("HISTORY_LIMIT", "500")
    s = Settings.from_env()
    assert s.history_limit == 500


# ── _load_full_history warning ──────────────────────────────────────


@pytest.mark.asyncio
async def test_load_full_history_warns_when_at_cap() -> None:
    """When ``list_for_thread`` returns exactly ``history_limit`` rows,
    a warning is logged so operators can spot a user who outgrew the
    default without trawling the LLM debug panel.

    We replace the service's logger with an in-memory Mock (rather than
    using pytest's ``caplog``) because the chat module's logger hierarchy
    interacts poorly with pytest's plugin when other tests in the suite
    have already poked the root logger — the warning is still emitted,
    but pytest's caplog propagation can swallow it under heavy test
    ordering.
    """
    from app.application.dto import MessageDTO
    from app.application.services.chat import ChatService

    msgs = [
        MessageDTO(id=i, role="user" if i % 2 else "assistant", content="x") for i in range(1, 6)
    ]

    settings = SimpleNamespace(history_limit=5)

    class FakeMessageRepo:
        async def list_for_thread(self, thread_id, limit):
            return msgs  # len == limit → warning fires

    svc = ChatService.__new__(ChatService)
    svc._settings = settings  # type: ignore[attr-defined]
    svc._messages = FakeMessageRepo()  # type: ignore[attr-defined]

    # Replace the module logger with a captured mock so we can assert
    # the warning fired regardless of pytest's caplog state.
    from unittest.mock import MagicMock

    fake_logger = MagicMock()
    # Patch the module's ``logger`` so the warning.call goes through
    # our mock. We import the module rather than the class so a
    # ``from ... import logger`` inside chat.py is also covered.
    import app.application.services.chat as chat_module

    original = chat_module.logger
    chat_module.logger = fake_logger
    try:
        result = await svc._load_full_history(thread_id=99)
    finally:
        chat_module.logger = original

    assert result == msgs
    fake_logger.warning.assert_called_once()
    msg = fake_logger.warning.call_args.args[0]
    assert "history_limit cap" in msg
    assert "raise HISTORY_LIMIT" in msg


@pytest.mark.asyncio
async def test_load_full_history_quiet_when_under_cap() -> None:
    """Below the cap: no warning. The verbose log would spam every
    short chat with a "99/100 used" line that drowns real signal.
    """
    from app.application.dto import MessageDTO
    from app.application.services.chat import ChatService

    msgs = [
        MessageDTO(id=i, role="user" if i % 2 else "assistant", content="x") for i in range(1, 6)
    ]

    settings = SimpleNamespace(history_limit=1000)

    class FakeMessageRepo:
        async def list_for_thread(self, thread_id, limit):
            return msgs  # len == 5, far below the 1000 cap

    svc = ChatService.__new__(ChatService)
    svc._settings = settings  # type: ignore[attr-defined]
    svc._messages = FakeMessageRepo()  # type: ignore[attr-defined]

    from unittest.mock import MagicMock

    fake_logger = MagicMock()
    import app.application.services.chat as chat_module

    original = chat_module.logger
    chat_module.logger = fake_logger
    try:
        result = await svc._load_full_history(thread_id=7)
    finally:
        chat_module.logger = original

    assert result == msgs
    fake_logger.warning.assert_not_called()


# ── UpdateConfigRequest accepts history_limit ──────────────────────


def test_update_config_request_accepts_history_limit() -> None:
    """``history_limit`` shows up in ``UpdateConfigRequest`` and the
    Pydantic ``ge=10`` floor is preserved end-to-end (so a hostile
    POST /api/config with history_limit=2 is rejected before it
    hits ``.env``).
    """
    from api.schemas import UpdateConfigRequest

    req = UpdateConfigRequest(history_limit=750)
    assert req.history_limit == 750

    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        UpdateConfigRequest(history_limit=2)


def test_update_config_request_history_limit_optional() -> None:
    """``None`` keeps the field absent so a partial PATCH (the Settings
    page's general save) doesn't wipe out the existing value.
    """
    from api.schemas import UpdateConfigRequest

    req = UpdateConfigRequest()
    assert req.history_limit is None
