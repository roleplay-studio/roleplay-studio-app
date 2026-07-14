"""Per-provider LLM subclasses (Phase 2).

Each provider is a thin subclass of ``BaseOpenAICompatibleLLM`` that
only declares its ``default_base_url`` and ``default_chat_model``.
The HTTP / streaming / reasoning logic lives in the base; subclasses
add no behaviour, only metadata.

This test loads each non-openrouter provider from
``api.constants.PROVIDERS`` and asserts that the corresponding
subclass wires the base to those defaults. We import the classes
through ``app.infrastructure.llm.providers`` — the test FAILS until
each provider module exists (Phase 2 of the LLM-provider plan).
"""

from __future__ import annotations

import pytest

from api.constants import PROVIDERS
from app.infrastructure.llm.base_openai import BaseOpenAICompatibleLLM

# Mapping from PROVIDERS id to the provider-subclass module path.
# OpenRouter is the Phase 1.3 reference implementation; this test
# covers the eight remaining OpenAI-compatible providers plus the
# "custom" shim (whose default_base_url is empty by design — picked
# up from the Settings.llm_base_url at runtime, not from PROVIDERS).
PROVIDER_MODULE_NAMES = {
    "openai": "app.infrastructure.llm.providers.openai",
    "lm-studio": "app.infrastructure.llm.providers.lm_studio",
    "deepseek": "app.infrastructure.llm.providers.deepseek",
    "gigachat": "app.infrastructure.llm.providers.gigachat",
    "grok": "app.infrastructure.llm.providers.grok",
    "kimi": "app.infrastructure.llm.providers.kimi",
    "minimax": "app.infrastructure.llm.providers.minimax",
    "yandexgpt": "app.infrastructure.llm.providers.yandexgpt",
    "z-ai": "app.infrastructure.llm.providers.z_ai",
}

EXPECTED_CLASS_NAMES = {
    "openai": "OpenAILLM",
    "lm-studio": "LMStudioLLM",
    "deepseek": "DeepSeekLLM",
    "gigachat": "GigaChatLLM",
    "grok": "GrokLLM",
    "kimi": "KimiLLM",
    "minimax": "MiniMaxLLM",
    "yandexgpt": "YandexGPTLLM",
    "z-ai": "ZAILLM",
}


@pytest.mark.parametrize("provider_id", sorted(PROVIDER_MODULE_NAMES))
def test_provider_subclass_module_exists_and_exports_class(provider_id: str) -> None:
    """Each provider in PROVIDERS has a subclass module that exports a CamelCaseLLM."""
    import importlib

    module = importlib.import_module(PROVIDER_MODULE_NAMES[provider_id])
    class_name = EXPECTED_CLASS_NAMES[provider_id]
    assert hasattr(module, class_name), (
        f"{PROVIDER_MODULE_NAMES[provider_id]} must export {class_name!r}"
    )


@pytest.mark.parametrize("provider_id", sorted(PROVIDER_MODULE_NAMES))
def test_provider_subclass_is_base_openai_compatible(provider_id: str) -> None:
    """Each subclass must inherit BaseOpenAICompatibleLLM so it shares the transport contract."""
    import importlib

    module = importlib.import_module(PROVIDER_MODULE_NAMES[provider_id])
    cls = getattr(module, EXPECTED_CLASS_NAMES[provider_id])
    assert issubclass(cls, BaseOpenAICompatibleLLM), (
        f"{EXPECTED_CLASS_NAMES[provider_id]} must inherit BaseOpenAICompatibleLLM"
    )


@pytest.mark.parametrize("provider_id", sorted(PROVIDER_MODULE_NAMES))
def test_provider_subclass_wires_default_base_url_from_providers(provider_id: str) -> None:
    """A subclass constructed with no base_url falls back to PROVIDERS[<id>]['default_base_url']."""
    import importlib

    expected = PROVIDERS[provider_id]["default_base_url"]
    if not expected:
        pytest.skip(f"{provider_id} has no default_base_url in PROVIDERS — handled by custom")

    module = importlib.import_module(PROVIDER_MODULE_NAMES[provider_id])
    cls = getattr(module, EXPECTED_CLASS_NAMES[provider_id])
    # Without passing base_url, the subclass should take it from PROVIDERS.
    instance = cls(api_key="sk-test", model="m")
    assert instance.base_url == expected.rstrip("/")


@pytest.mark.parametrize("provider_id", sorted(PROVIDER_MODULE_NAMES))
def test_provider_subclass_default_model_matches_providers(provider_id: str) -> None:
    """The default model declared in PROVIDERS is the one the subclass uses."""
    import importlib

    expected_model = PROVIDERS[provider_id]["default_model"]
    module = importlib.import_module(PROVIDER_MODULE_NAMES[provider_id])
    cls = getattr(module, EXPECTED_CLASS_NAMES[provider_id])
    instance = cls(api_key="sk-test")
    assert instance.model == expected_model


def test_all_provider_subclasses_are_in_provider_package_dunder_all() -> None:
    """``app.infrastructure.llm.providers`` re-exports every subclass
    so the bootstrap factory can find them by string id (Phase 3)."""
    import app.infrastructure.llm.providers as providers_pkg

    for provider_id, expected_class_name in EXPECTED_CLASS_NAMES.items():
        assert hasattr(providers_pkg, expected_class_name), (
            f"providers.{expected_class_name} must be importable for the "
            f"bootstrap factory dispatch in Phase 3"
        )
