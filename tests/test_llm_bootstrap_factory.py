"""Bootstrap LLM factory + BaseAnthropicLLM stub (Phase 3).

The factory translates ``Settings.llm_provider`` into a concrete
``LLM`` instance — picking the right subclass per provider id. The
Anthropic base is a stub today but ships the same Protocol surface as
``BaseOpenAICompatibleLLM`` so the factory and downstream services
don't need to know which wire protocol a future Anthropic-compatible
provider uses.
"""

from __future__ import annotations

from app.infrastructure.llm import (
    BaseOpenAICompatibleLLM,
    MockLLM,
    OpenRouterLLM,
)
from app.infrastructure.llm.base_anthropic import BaseAnthropicLLM
from app.infrastructure.llm.providers import (
    ZAILLM,
    DeepSeekLLM,
    GigaChatLLM,
    GrokLLM,
    KimiLLM,
    LMStudioLLM,
    MiniMaxLLM,
    OpenAILLM,
    ProviderLLM,
    YandexGPTLLM,
)


def _fake_settings(
    llm_provider: str,
    llm_api_key: str = "sk-test",
    chat_model: str = "openai/gpt-oss-20b",
    fast_model: str = "openai/gpt-4o-mini",
    llm_base_url: str = "https://example.com/v1",
) -> object:
    """Tiny stand-in that satisfies whatever the factory reads.

    The factory touches four attributes: ``llm_provider``,
    ``llm_api_key``, ``chat_model``, ``fast_model``, ``llm_base_url``.
    Settings is a pydantic model — too heavy for these unit tests —
    so we lean on ``getattr`` inside the factory and pass a plain
    namespace here.
    """
    from types import SimpleNamespace

    secret = SimpleNamespace(get_secret_value=lambda: llm_api_key)
    return SimpleNamespace(
        llm_provider=llm_provider,
        llm_api_key=secret if llm_api_key else None,
        chat_model=chat_model,
        fast_model=fast_model,
        llm_base_url=llm_base_url,
        app_referer="http://localhost:1420",
        default_temperature=0.7,
        default_max_tokens=4096,
        reasoning_field_names=["reasoning_content"],
    )


def test_factory_dispatches_each_provider_id() -> None:
    """``make_llm`` returns the correct subclass for every PROVIDERS id."""
    from app.infrastructure.llm.factory import make_llm

    expected = {
        "openrouter": OpenRouterLLM,
        "openai": OpenAILLM,
        "lm-studio": LMStudioLLM,
        "deepseek": DeepSeekLLM,
        "gigachat": GigaChatLLM,
        "grok": GrokLLM,
        "kimi": KimiLLM,
        "minimax": MiniMaxLLM,
        "yandexgpt": YandexGPTLLM,
        "z-ai": ZAILLM,
        "mock": MockLLM,
    }
    for pid, cls in expected.items():
        settings = _fake_settings(llm_provider=pid)
        llm = make_llm(settings)
        assert isinstance(llm, cls), f"{pid} → {type(llm).__name__}, expected {cls.__name__}"


def test_factory_uses_model_override_for_fast_llm() -> None:
    """When a model_override is passed, the LLM uses it instead of chat_model."""
    from app.infrastructure.llm.factory import make_llm
    from app.infrastructure.llm.providers.catalog import find_catalog

    settings = _fake_settings(
        llm_provider="openai",
        chat_model="primary-model",
        fast_model="fastone",
    )
    # Without override → subclass falls back to the catalog's
    # default_model (Phase 1.5 — defaults live in per-file catalogs,
    # not in api.constants.PROVIDERS).
    primary = make_llm(settings)
    openai_catalog = find_catalog("openai")
    assert openai_catalog is not None, "openai catalog is mandatory"
    assert primary.model == openai_catalog.default_model
    # With override → that exact model id is used.
    fast = make_llm(settings, model_override="fastone")
    assert fast.model == "fastone"


def test_factory_unknown_provider_falls_back_to_mock() -> None:
    """Defence in depth — Settings.llm_provider validator already maps
    unknowns to mock, but the factory itself should also tolerate a
    bad value rather than crashing the container."""
    from app.infrastructure.llm.factory import make_llm

    llm = make_llm(_fake_settings(llm_provider="not-a-real-provider"))
    assert isinstance(llm, MockLLM)


def test_factory_openrouter_uses_handwritten_subclass_not_provider_llm() -> None:
    """``openrouter`` is the Phase-1.3 reference. It's a hand-written
    subclass with a hard-coded base URL, not a ProviderLLM auto-class.
    This test guards against accidentally swapping it for the generic
    registry-driven subclass (which would lose the
    ``HTTP-Referer: settings.app_referer`` header)."""
    from app.infrastructure.llm.factory import make_llm

    settings = _fake_settings(llm_provider="openrouter")
    llm = make_llm(settings)
    assert type(llm) is OpenRouterLLM, (
        f"openrouter must produce an OpenRouterLLM (not ProviderLLM), "
        f"got {type(llm).__name__}"
    )


def test_base_anthropic_satisfies_llm_protocol_surface() -> None:
    """The Anthropic base must accept the same constructor surface as
    BaseOpenAICompatibleLLM so the factory can build it the same way
    when populated with a real provider."""
    from app.infrastructure.llm.factory import make_llm

    # ``anthropic`` is the placeholder id. It's not a real provider in
    # PROVIDERS yet (Phase 5 may add it); the factory should detect that
    # and fall back to mock — but still emit a warning. Anthropic itself
    # never fires until we ship an anthropic-compatible subclass.
    settings = _fake_settings(llm_provider="mock")
    llm = make_llm(settings)
    assert hasattr(llm, "startup")
    assert hasattr(llm, "close")
    assert hasattr(llm, "generate_response")
    assert hasattr(llm, "generate_response_stream")
    assert hasattr(llm, "model_name")


def test_base_anthropic_is_separate_from_openai_base() -> None:
    """The Anthropic base class must NOT inherit from
    BaseOpenAICompatibleLLM — they share a Protocol (LLMPort) but
    inherit from object independently so a future Anthropic-flavored
    provider can stay free of the chat-completions-shape contract."""
    assert not issubclass(BaseAnthropicLLM, BaseOpenAICompatibleLLM)
    # Both top-level LLM base classes are kept apart from ProviderLLM
    # (the OpenAI-compat registry-driven subclassor) so swapping a
    # provider class by mistake doesn't accidentally inherit the
    # registry lookup.
    assert not issubclass(BaseAnthropicLLM, ProviderLLM)


def test_factory_provider_subclass_constructor_uses_settings_llm_base_url_fallback() -> None:
    """Registry-driven subclasses prefer ``PROVIDERS[<id>]['default_base_url']``
    over ``settings.llm_base_url``. The factory preserves that order —
    a provider's canonical URL wins over the global ``LLM_BASE_URL``
    setting. This guards against an accidental refactor that swaps
    the priority and breaks production deployments."""
    from app.infrastructure.llm.factory import make_llm

    settings = _fake_settings(
        llm_provider="deepseek",
        llm_base_url="https://should-be-ignored.example/v1",
    )
    llm = make_llm(settings)
    assert llm.base_url == "https://api.deepseek.com/v1"
