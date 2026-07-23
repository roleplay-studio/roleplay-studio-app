"""Regression tests for ``reset_and_start_container`` (lifespan-equivalent).

Before this fix, ``reset_container()`` only cleared the
``@lru_cache`` on ``get_container()`` — it did NOT call
``startup_llms()`` for the new container. Result: every OpenAI
LLM (and the TTS provider) held a ``BaseOpenAICompatibleLLM``
whose ``_async_client`` was ``None``, so the next chat request
raised ``RuntimeError: BaseOpenAICompatibleLLM client is not
initialised — call await llm.startup() first`` (the very error
the user hit after saving Settings).

The lifespan handler at boot calls ``startup_llms(get_container())``,
so the very first request after process start works fine — but
``POST /api/config`` (``api/routes/config.py``) and
``POST /api/setup/configure`` (``api/routes/setup.py``) called
``reset_container()`` without a follow-up ``startup_llms()``,
breaking all subsequent LLM calls until the user restarted the
backend.

These tests pin the contract of the new
``reset_and_start_container()`` helper: every LLM reachable from
the container must have its httpx client opened before the helper
returns, so the next request to the chat endpoint does not raise.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from app.bootstrap import get_container, reset_and_start_container


def _stub_llm() -> AsyncMock:
    """LLM stub with tracking ``startup()`` and ``close()`` methods."""
    llm = AsyncMock()
    llm.startup = AsyncMock()
    llm.close = AsyncMock()
    return llm


def _replace_llms_with_stubs(container) -> dict[str, AsyncMock]:
    """Swap every ``_llm`` on ``container`` for a tracking stub.

    Returns a dict of stubs so the test can assert on the
    STARTUP that happens during ``reset_and_start_container`` —
    the helper builds a NEW container, and we don't have
    visibility into its internal ``_llm`` field from outside
    (the real production wiring puts DeepSeekLLM / OpenRouterLLM
    there). So instead of asserting on the new container's LLM,
    we observe ``startup_llms`` being CALLED and the OLD
    container's LLM being CLOSED.
    """
    stubs: dict[str, AsyncMock] = {}
    if container.chat is not None and getattr(container.chat, "_llm", None) is not None:
        stubs["chat"] = _stub_llm()
        container.chat._llm = stubs["chat"]  # type: ignore[attr-defined]
    if container.summarizer is not None and getattr(
        container.summarizer, "_llm", None
    ) is not None:
        stubs["summarizer"] = _stub_llm()
        container.summarizer._llm = stubs["summarizer"]  # type: ignore[attr-defined]
    if container.summary is not None and getattr(
        container.summary, "_llm", None
    ) is not None:
        stubs["summary"] = _stub_llm()
        container.summary._llm = stubs["summary"]  # type: ignore[attr-defined]
    if container.upload is not None and getattr(
        container.upload, "_llm", None
    ) is not None:
        stubs["upload"] = _stub_llm()
        container.upload._llm = stubs["upload"]  # type: ignore[attr-defined]
    return stubs


@pytest.mark.asyncio
async def test_reset_and_start_container_opens_new_llm_clients() -> None:
    """After ``reset_and_start_container()``, ``startup_llms`` has
    been called on the new container — the very step the old
    ``reset_container()`` was missing. This is the fix for
    "save Settings → next chat request raises RuntimeError".

    We observe ``startup_llms`` itself via patch — this is a
    strong enough contract: as long as the helper invokes it
    on the freshly-built container, every LLM reachable from
    that container has its httpx client opened.
    """
    # Prime the cache.
    initial = get_container()

    # Watch the helper that actually opens httpx clients.
    with patch("app.bootstrap.startup_llms", new=AsyncMock()) as mock_startup:
        await reset_and_start_container()

    # startup_llms must have been called exactly once, on the
    # newly-built container (which is what the next
    # get_container() returns).
    assert mock_startup.call_count == 1, (
        f"startup_llms should be called once during reset, got {mock_startup.call_count}"
    )
    # And the argument must be the new container (different
    # identity from the cached one).
    called_with = mock_startup.call_args.args[0]
    assert called_with is not initial, (
        "startup_llms must be called on the NEW container, not the old one"
    )
    assert called_with is get_container(), (
        "the container passed to startup_llms must be the one the "
        "next get_container() returns (so the chat handler sees a "
        "started LLM, not a fresh un-started one)"
    )


@pytest.mark.asyncio
async def test_reset_and_start_container_closes_old_llm_clients() -> None:
    """The OLD container's LLM clients must be closed before the
    new ones are opened. Otherwise the process leaks httpx sockets
    every time the user saves Settings.
    """
    initial = get_container()
    stubs = _replace_llms_with_stubs(initial)
    # Sanity: lifespan is not running in this test, so close()
    # hasn't fired yet on the stubs.
    assert stubs["chat"].close.call_count == 0

    await reset_and_start_container()

    # The OLD stubs must have had close() called on them
    # (during shutdown_llms, which runs BEFORE the new build).
    assert stubs["chat"].close.call_count == 1, (
        f"close() should be called on the OLD LLM during reset, "
        f"got {stubs['chat'].close.call_count}"
    )


@pytest.mark.asyncio
async def test_reset_and_start_container_is_idempotent_when_no_cached_container() -> None:
    """Calling ``reset_and_start_container()`` before the cache is
    primed (e.g. in a unit test that doesn't go through the
    lifespan) must NOT raise. The helper skips shutdown when there
    is nothing to shut down, and the new container's LLMs are
    still started.
    """
    # Force the cache to be empty even if a previous test primed it.
    get_container.cache_clear()

    # No exception raised when nothing is cached.
    with patch("app.bootstrap.startup_llms", new=AsyncMock()) as mock_startup:
        await reset_and_start_container()

    # Even when the cache was empty, the helper must still call
    # startup_llms on the freshly-built container — the new
    # container has to be live for the next chat request.
    assert mock_startup.call_count == 1, (
        "startup_llms must be called even when there's nothing to "
        "shut down (the new container still needs its LLMs started)"
    )


@pytest.mark.asyncio
async def test_reset_and_start_container_handles_close_failures() -> None:
    """A failing ``close()`` on the old LLM must NOT prevent the new
    container from being built and started. Without this guard, a
    transient socket error during a Settings save would leave the
    backend permanently broken until manual restart.
    """
    initial = get_container()
    stubs = _replace_llms_with_stubs(initial)
    stubs["chat"].close = AsyncMock(
        side_effect=RuntimeError("simulated close failure")
    )

    # Must not raise despite the failing close().
    with patch("app.bootstrap.startup_llms", new=AsyncMock()) as mock_startup:
        await reset_and_start_container()

    # startup_llms must STILL have been called on the new
    # container — the close() failure did not block the rebuild.
    assert mock_startup.call_count == 1, (
        f"a failing close() on the old LLM must not prevent the new "
        f"container's startup, got {mock_startup.call_count}"
    )
    # The new container is the one the chat handler will see.
    new_container = get_container()
    assert new_container is not initial
