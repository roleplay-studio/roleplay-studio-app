"""Tests for ``_format_exception_detail`` in chat.py.

The helper formats an exception as a user-visible string for the
chat UI's error bubble. The contract is: include the exception
type, the message, the deepest ``OSError`` cause (so users see
``[Errno 61] Connection refused`` rather than a generic
"ConnectError: All connection attempts failed"), the configured
``LLM_BASE_URL`` (so the user can sanity-check the endpoint
from the alert alone), and a short ``[ref: xxxxxxxx]`` token
for log cross-referencing.

If the format ever drops one of these — e.g. someone refactors
out the ``OSError`` walk and the user only sees the wrapper
type — the user gets stuck staring at "ConnectError: All
connection attempts failed" with no actionable detail. These
tests pin every element of the contract.
"""

from __future__ import annotations

import pytest

from app.application.services.chat import _format_exception_detail


class _FakeOSError(OSError):
    """OSError subclass that always returns a stable errno+str.

    The real ``OSError`` str varies by platform ([Errno N] on
    POSIX, [WinError N] on Windows). For unit tests we want
    deterministic strings so the assertions are stable across
    CI runners.
    """

    def __init__(self, errno: int, msg: str) -> None:
        super().__init__(errno, msg)
        self._msg = msg

    def __str__(self) -> str:  # pragma: no cover - exercised via detail
        return self._msg


def test_includes_exception_type_name() -> None:
    detail = _format_exception_detail(ValueError("bad input"))
    assert "ValueError" in detail
    assert "bad input" in detail


def test_includes_oserror_cause_with_errno_style_message() -> None:
    # Simulate a typical network failure: ``httpx.ConnectError``
    # wrapping a real ``OSError`` with errno 61 (Connection
    # refused on macOS).
    inner = _FakeOSError(61, "Connection refused")
    try:
        raise inner
    except OSError as e:
        try:
            raise RuntimeError("All connection attempts failed") from e
        except RuntimeError as outer:
            detail = _format_exception_detail(outer)

    assert "RuntimeError" in detail
    assert "All connection attempts failed" in detail
    # The cause chain walk surfaces the OSError with its str.
    assert "Connection refused" in detail


def test_walks_context_link_set_by_bare_raise() -> None:
    # ``raise X from Y`` sets ``__cause__``; a bare ``raise X``
    # inside an ``except`` block sets ``__context__`` instead.
    # The helper walks both via ``cur.__cause__ or cur.__context__``,
    # so an OSError surfaced through __context__ must still appear
    # in the formatted detail.

    # Branch 1: __cause__ (raise from) — capture outer in a
    # try/except so the test doesn't actually propagate.
    inner = _FakeOSError(111, "Connection refused")
    outer_from: RuntimeError
    try:
        try:
            raise inner
        except OSError as e:
            raise RuntimeError("wrap") from e
    except RuntimeError as caught:
        outer_from = caught
    assert "Connection refused" in _format_exception_detail(outer_from)

    # Branch 2: __context__ (bare raise) — same structure.
    inner2 = _FakeOSError(111, "Connection refused")
    outer_ctx: RuntimeError
    try:
        try:
            raise inner2
        except OSError:
            raise RuntimeError("wrap")
    except RuntimeError as caught:
        outer_ctx = caught
    assert "Connection refused" in _format_exception_detail(outer_ctx)


def test_includes_llm_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    # We can't easily change the global Settings singleton from
    # here without breaking other tests, so just assert that
    # the URL from the test environment shows up if it's
    # configured. The CI test runner sets LLM_BASE_URL (or
    # doesn't); the helper is supposed to add it conditionally.
    from app.infrastructure.config import Settings

    base = Settings.from_env().llm_base_url
    if not base:
        pytest.skip("LLM_BASE_URL not configured in test env")

    detail = _format_exception_detail(RuntimeError("boom"))
    assert f"target: {base}" in detail


def test_includes_short_request_id() -> None:
    detail = _format_exception_detail(RuntimeError("x"))
    # 8 hex chars between [ref: and ]. Cheap to grep; enough
    # entropy to be unique within a single failure cluster.
    assert "[ref: " in detail
    ref_token = detail.split("[ref: ")[1].split("]")[0]
    assert len(ref_token) == 8
    assert all(c in "0123456789abcdef" for c in ref_token)


def test_each_call_generates_a_distinct_ref() -> None:
    # Two consecutive failures should not share a ref token —
    # otherwise the user can't tell "this is a new failure" from
    # "this is the same failure I just retried". The helper
    # generates a fresh uuid per call, so the tokens differ
    # (with probability 1 - 2^-32).
    a = _format_exception_detail(RuntimeError("first"))
    b = _format_exception_detail(RuntimeError("second"))
    assert a != b


def test_works_on_exception_with_no_message() -> None:
    # Some exceptions (e.g. KeyboardInterrupt) have empty str().
    # The helper should still produce a non-empty detail.
    detail = _format_exception_detail(RuntimeError(""))
    assert "RuntimeError" in detail
    assert "[ref: " in detail


def test_does_not_raise_when_settings_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # If the ``Settings.from_env()`` call inside the helper
    # raises (e.g. during very early startup), the helper must
    # still produce a usable detail string. We simulate by
    # patching the imported name to throw.
    import app.application.services.chat as chat_module

    class _BoomSettings:
        @staticmethod
        def from_env() -> None:
            raise RuntimeError("settings unavailable")

    monkeypatch.setattr(chat_module, "Settings", _BoomSettings)
    # Helper imports Settings lazily inside the function, but
    # we already imported it at module level via ``from
    # app.infrastructure.config import Settings``. To override
    # the inner reference, we patch the module attribute on
    # the source module too.
    import app.infrastructure.config as cfg

    monkeypatch.setattr(cfg, "Settings", _BoomSettings)

    # Should NOT raise — the helper has a try/except around the
    # Settings call. The detail should still include the
    # exception type and ref token.
    detail = _format_exception_detail(RuntimeError("x"))
    assert "RuntimeError" in detail
    assert "[ref: " in detail

