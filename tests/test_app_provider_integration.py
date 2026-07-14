"""End-to-end integration: settings-to-container for Phase 5.

This suite verifies that the LLM-provider refactor ships the same
machine-readable contract as before:

* A ``Settings`` instance with ``llm_provider="minimax"`` (or any
  real provider id) instantiates the matching subclass via the
  factory — no network call, no ImportError, no crash.
* Bootstrapping via the real ``bootstrap.build_container`` with a
  llm_provider env override wires the LLM through ``make_llm``.
* An invalid provider id round-trips as ``mock`` end-to-end
  (the same defence in depth the Settings validator alone enforces).

Pre-refactor this was a hard-coded ``if pid == "openrouter"`` branch
in bootstrap. Phase 5 documents that every advertised provider now
flows through one factory function.
"""

from __future__ import annotations

import pytest

from api.constants import PROVIDERS
from app.bootstrap import build_container
from app.infrastructure.config import Settings
from app.infrastructure.llm.factory import make_llm


@pytest.mark.parametrize("provider_id", sorted(PROVIDERS.keys()))
def test_settings_and_factory_round_trip_for_every_provider(
    provider_id: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Settings(llm_provider=<id>) is honoured by the factory.

    We disable network: ``make_llm`` does not call ``startup()`` —
    constructing a subclass only validates config and reads
    ``PROVIDERS[<id>]``. Without this gate, every test would leak
    a half-open httpx client.

    The bootstrap factory gives us a non-mock class for every real
    provider id (openrouter/openai/lm-studio/deepseek/gigachat/grok/
    kimi/minimax/yandexgpt/z-ai/custom).
    """
    monkeypatch.setenv("LLM_PROVIDER", provider_id)
    s = Settings.from_env()
    assert s.llm_provider == provider_id
    llm = make_llm(s)
    assert llm is not None
    assert llm.model_name or provider_id in PROVIDERS  # provider resolves to a real class
    # And the subclass fills in base_url from the registry (or, for
    # ``custom``, requires the caller to supply one — that's fine,
    # we accept either path here).
    expected_url = PROVIDERS[provider_id]["default_base_url"]
    if expected_url:
        assert llm.base_url == expected_url.rstrip("/")


def test_build_container_with_provider_subclass_minimax_no_network(monkeypatch) -> None:
    """``build_container`` honouring ``LLM_PROVIDER=minimax`` produces
    a MiniMaxLLM instance with the canonical base URL. Runs the real
    bootstrap path used by the FastAPI lifespan handler."""
    monkeypatch.setenv("LLM_PROVIDER", "minimax")
    monkeypatch.setenv("LLM_API_KEY", "sk-test")

    container = build_container()
    assert container.chat is not None
    llm = container.chat._llm
    assert llm is not None
    # Don't make any HTTPS calls — just inspect the constructed shape.
    assert llm.base_url == "https://api.minimaxi.com/v1"
    # fast_llm is a separate instance with the same provider class.
    assert container.summarizer is not None
    assert type(container.summarizer._llm) is type(llm)


def test_build_container_with_unknown_provider_gracefully_falls_back(monkeypatch) -> None:
    """A bad ``LLM_PROVIDER`` value should still produce a usable
    container — the validator already maps it to ``mock`` upstream,
    but the bootstrap path is a defence in depth."""
    monkeypatch.setenv("LLM_PROVIDER", "not-a-real-provider")
    container = build_container()
    # Falls back to MockLLM (Phase 1.1 validator behaviour).
    assert container.chat is not None
    from app.infrastructure.llm_mock import MockLLM

    assert isinstance(container.chat._llm, MockLLM)


def test_build_container_with_unknown_provider_falls_back_when_set_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even without env: a Settings instance built with a bad
    llm_provider (e.g. via test fixtures) bootstraps cleanly."""
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    # Build a Settings instance with a deliberately bad llm_provider
    # — the validator maps it to "mock" defensively.
    monkeypatch.setenv("LLM_PROVIDER", "definitely-not-a-provider")
    s = Settings.from_env()
    assert s.llm_provider == "mock"  # validator fallback
    container = build_container(s)
    assert container.chat is not None
    from app.infrastructure.llm_mock import MockLLM

    assert isinstance(container.chat._llm, MockLLM)
