"""Unit tests for ``MockLLM`` — the deterministic in-process LLM simulator.

Verifies the wire shape that downstream code (orchestrator,
``generate_response_stream`` callers, FastAPI SSE route, frontend SSE
parser, dev-mode LLM debug modal) relies on. If any of these
invariants drift, ``MockLLM`` no longer impersonates ``OpenRouterLLM``
and the E2E suite that depends on it will start failing in confusing
ways.

Coverage areas:

* ``generate_response`` returns a deterministic string
* ``generate_response_stream`` yields per-character content chunks
* The terminal chunk carries a 3-key ``usage`` dict (matching the
  ``_extract_usage`` contract on the real provider)
* ``model_name`` is a non-empty string distinct from the real
  ``chat_model`` default
* Lifecycle (``startup``/``close``) is idempotent and never raises
"""

from __future__ import annotations

import pytest

from app.infrastructure.config import Settings
from app.infrastructure.llm_mock import (
    DEFAULT_RESPONSE_PREFIX,
    MockLLM,
    _compose_response,
    _last_user_text,
)

# ── Helpers ────────────────────────────────────────────────────────


def _settings() -> Settings:
    """Build Settings with no .env / _env_file so test runs are
    hermetic and don't accidentally pick up the operator's LLM key.

    Uses ``_env_file=None`` because the existing Settings dataclass
    follows pydantic-settings conventions; passing an explicit ``None``
    for ``_env_file`` disables the auto-load that Settings.from_env()
    does by default.
    """
    # Re-using Settings.from_env() is fine for the mock path because
    # llm_provider=mock short-circuits the API-key requirement. The
    # Settings() default constructor also works; use it to avoid
    # touching the operator's real .env by accident.
    return Settings(_env_file=None)


# ── _compose_response / _last_user_text ────────────────────────────


def test_compose_response_with_user_message_echoes_user_text() -> None:
    """The assistant string includes the echoed user message.

    Tests that assert on persisted-message content (e.g.
    ``tests/critical/04-state-regenerate.spec.ts`` wants to verify a
    specific assistant reply) depend on this echo.
    """
    msgs = [{"role": "user", "content": "Tell me about dragons"}]
    out = _compose_response(msgs)
    assert out.startswith(DEFAULT_RESPONSE_PREFIX)
    assert "Tell me about dragons" in out


def test_compose_response_without_user_message_uses_default_prefix_only() -> None:
    """With no user turn in history, fall back to the default prefix.

    This is the case the orchestrator hits when only the system
    prompt + dynamic prompt have been assembled so far — it must
    still emit a non-empty response so the SSE stream surfaces text
    to the frontend.
    """
    msgs: list[dict[str, str]] = [
        {"role": "system", "content": "You are a dragon."},
        {"role": "assistant", "content": "Hello there."},
    ]
    out = _compose_response(msgs)
    assert out == DEFAULT_RESPONSE_PREFIX.strip()


def test_compose_response_picks_last_user_in_conversation() -> None:
    """Multi-turn conversations echo the most recent user message,
    not the first one. Frontend multi-turn tests rely on this.
    """
    msgs = [
        {"role": "user", "content": "first turn"},
        {"role": "assistant", "content": "first reply"},
        {"role": "user", "content": "second turn"},
    ]
    out = _compose_response(msgs)
    assert "second turn" in out
    assert "first turn" not in out


def test_last_user_text_skips_non_user_roles() -> None:
    """``_last_user_text`` walks backwards and returns the newest
    user-role content, ignoring system / assistant messages that may
    sit in between.
    """
    msgs = [
        {"role": "system", "content": "sys1"},
        {"role": "user", "content": "first user"},
        {"role": "assistant", "content": "asst1"},
        {"role": "user", "content": "second user"},
    ]
    assert _last_user_text(msgs) == "second user"


def test_last_user_text_returns_empty_when_no_user_messages() -> None:
    msgs = [
        {"role": "system", "content": "only system"},
        {"role": "assistant", "content": "only assistant"},
    ]
    assert _last_user_text(msgs) == ""


# ── generate_response ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_response_returns_composed_string() -> None:
    """``generate_response`` returns the same string ``_compose_response``
    computes (so non-streaming callers — summarizer, fast_llm routes —
    see byte-identical output to the streaming path's concatenated
    chunks).
    """
    llm = MockLLM(settings=_settings())
    out = await llm.generate_response([{"role": "user", "content": "hi there"}])
    expected = _compose_response([{"role": "user", "content": "hi there"}])
    assert out == expected
    assert "hi there" in out


# ── generate_response_stream ───────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_response_stream_yields_one_chunk_per_char() -> None:
    """Per-character chunking is the whole point — the SSE wire shape
    that frontend/e2e/lib/sse.ts counts events on. If we coalesced to
    one chunk, the stream would look like a non-streaming response and
    the test helpers' ``expectStream(page, /token/, …)`` helper would
    race past the ``data:`` events it watches for.
    """
    # Zero-out the stream delay so the test is <10 ms total rather
    # than N * 5 ms — we are testing chunking, not timing.
    llm = MockLLM(settings=_settings())
    llm.stream_delay_s = 0

    chunks = []
    async for c in llm.generate_response_stream([{"role": "user", "content": "x"}]):
        chunks.append(c)

    # One chunk per char + 1 terminal usage chunk.
    text = _compose_response([{"role": "user", "content": "x"}])
    assert len(chunks) == len(text) + 1


@pytest.mark.asyncio
async def test_generate_response_stream_terminal_chunk_has_usage() -> None:
    """The last chunk carries the 3-key usage dict — matching the
    ``_extract_usage`` shape on the real OpenRouter wire. The dev-mode
    LLM debug modal reads these exact keys; if we drop one, the modal
    shows ``NaN`` token counts.
    """
    llm = MockLLM(settings=_settings())
    llm.stream_delay_s = 0

    chunks = [c async for c in llm.generate_response_stream([{"role": "user", "content": "ab"}])]
    last = chunks[-1]
    assert last.usage is not None
    assert set(last.usage.keys()) == {
        "completion_tokens",
        "prompt_tokens",
        "total_tokens",
    }
    # All counts are positive ints (the mock floors at 1 so a 0-char
    # message does not show as "0 prompt tokens", which would be a
    # weird rendering in the UI).
    for v in last.usage.values():
        assert isinstance(v, int)
        assert v >= 1


@pytest.mark.asyncio
async def test_generate_response_stream_terminal_chunk_has_empty_content() -> None:
    """The usage chunk has empty content — it is purely metadata. If
    we accidentally echo the assistant's last char here, the frontend
    would render one duplicated character at the end of the
    assistant bubble.
    """
    llm = MockLLM(settings=_settings())
    llm.stream_delay_s = 0
    chunks = [c async for c in llm.generate_response_stream([{"role": "user", "content": "hello"}])]
    assert chunks[-1].content == ""


@pytest.mark.asyncio
async def test_generate_response_stream_concat_matches_non_streaming() -> None:
    """Joining the streamed chunks yields the same string as
    ``generate_response`` — keeping the two surfaces in lockstep is
    the whole point of having a single ``_compose_response``.
    """
    llm = MockLLM(settings=_settings())
    llm.stream_delay_s = 0
    streamed_chunks = [
        c async for c in llm.generate_response_stream([{"role": "user", "content": "compare"}])
    ]
    streamed_text = "".join(c.content for c in streamed_chunks)
    non_streamed = await llm.generate_response([{"role": "user", "content": "compare"}])
    assert streamed_text == non_streamed


@pytest.mark.asyncio
async def test_generate_response_stream_no_reasoning_field() -> None:
    """MockLLM does not emit reasoning; the contract with
    ``OpenRouterLLM._split_delta`` is that ``reasoning`` is ``None``
    unless explicitly set. Tests downstream assert ``delta.content``
    is non-empty without inspecting reasoning.
    """
    llm = MockLLM(settings=_settings())
    llm.stream_delay_s = 0
    chunks = [
        c async for c in llm.generate_response_stream([{"role": "user", "content": "no reasoning"}])
    ]
    assert all(c.reasoning is None for c in chunks)


# ── Lifecycle / metadata ───────────────────────────────────────────


def test_model_name_is_distinct_from_real_chat_model() -> None:
    """``model_name`` must look obviously fake so a developer who
    sees it in the dev-mode LLM debug modal immediately knows the
    response came from the simulator.
    """
    llm = MockLLM(settings=_settings())
    assert llm.model_name
    assert llm.model_name != llm.settings.chat_model
    # Conventional pattern — proxy route + version. Visible in modal.
    assert "/" in llm.model_name


def test_api_key_is_empty_string_for_protocol_parity() -> None:
    """``api_key`` must be the empty string (not ``None``) so
    ``OpenRouterLLM._get_headers`` branch logic — which inspects
    ``self.api_key`` against the sentinel — continues to behave the
    same even though the mock never sends an HTTP request.
    """
    llm = MockLLM(settings=_settings())
    assert llm.api_key == ""


@pytest.mark.asyncio
async def test_startup_and_close_are_idempotent() -> None:
    """The FastAPI lifespan handler calls ``startup()`` /
    ``close()`` on every LLM; the mock must tolerate both a second
    call and a missing-call order without raising. The real
    ``OpenRouterLLM`` is also idempotent here (see docs/review.md K2)
    so we keep the contract symmetric.
    """
    llm = MockLLM(settings=_settings())
    await llm.startup()
    await llm.startup()  # second time → no-op
    await llm.close()
    await llm.close()  # second time → no-op


def test_mock_accepts_api_key_kwarg_for_bootstrap_symmetry() -> None:
    """bootstrap.py builds fast_llm with the same kwargs as llm.
    Both branches (``OpenRouterLLM`` / ``MockLLM``) must accept
    ``api_key`` as a positional kwarg — otherwise the
    ``settings.llm_provider == "mock"`` branch and the fallback
    branch would diverge. This test pins that the kwarg is
    accepted and ignored.
    """
    llm = MockLLM(api_key="sk-should-be-ignored", settings=_settings())
    assert llm.api_key == ""  # mock never stores the operator's key
