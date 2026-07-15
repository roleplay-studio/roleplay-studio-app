"""Provider catalog: per-file metadata replacing PROVIDERS dict.

Each ``app/infrastructure/llm/providers/<id>.py`` module declares a
:class:`ProviderCatalog` instance with default_base_url, default_model,
available_models (the list of model ids the operator can pick in the
wizard's dropdown), and the SetupWizard flags. The boot-time factory
pulls defaults from the catalog (no string-keyed registry lookup),
and the ``/api/setup/providers`` route rebuilds the wizard-facing
list by introspecting every catalog in the providers package.

This file pins both contracts:

* Every concrete provider subclass exposes a ``catalog`` attribute.
* The catalog has the shape the SetupWizard frontend expects.
* ``available_models`` is a non-empty list (a provider with one
  supported model ships it as a 1-element list, not the magic
  empty-string — that bypassed the model picker before).
* Catalog defaults keep working in the bootstrap factory without
  requiring ``PROVIDERS`` from ``api.constants``.
"""

from __future__ import annotations

import pytest

from app.infrastructure.llm.providers import (
    ZAILLM,
    DeepSeekLLM,
    GigaChatLLM,
    GrokLLM,
    KimiLLM,
    LMStudioLLM,
    MiniMaxLLM,
    OpenAILLM,
    OpenRouterLLM,
    YandexGPTLLM,
)
from app.infrastructure.llm.providers.yandexgpt import catalog as yandexgpt_catalog

CONCRETE_PROVIDERS = [
    OpenRouterLLM,
    OpenAILLM,
    LMStudioLLM,
    DeepSeekLLM,
    GigaChatLLM,
    GrokLLM,
    KimiLLM,
    MiniMaxLLM,
    YandexGPTLLM,
    ZAILLM,
]


@pytest.mark.parametrize("cls", CONCRETE_PROVIDERS)
def test_provider_catalog_is_a_provider_catalog_instance(cls) -> None:
    """Every concrete provider exposes a ``catalog`` class attribute."""
    catalog = getattr(cls, "catalog", None)
    assert catalog is not None, (
        f"{cls.__name__} must declare a ProviderCatalog instance as `catalog` "
        "so the bootstrap factory and /api/setup/providers route can read its "
        "defaults from the module itself rather than from a side registry."
    )
    assert catalog.provider_id == cls.provider_id


def test_yandexgpt_catalog_metadata_lives_in_its_own_file() -> None:
    """The YandexGPT catalog must round-trip the fields a Russian operator
    actually needs in the SetupWizard: canonical base URL, default model,
    the full list of supported yandexgpt model ids (so the wizard can
    offer a dropdown rather than a free-text box), IAM-flag flag."""
    cat = yandexgpt_catalog
    assert cat.provider_id == "yandexgpt"
    assert cat.label == "YandexGPT"
    assert cat.default_base_url == "https://llm.api.cloud.yandex.net/foundationModels/v1"
    assert cat.default_model == "yandexgpt/latest"
    assert isinstance(cat.available_models, (list, tuple))
    assert len(cat.available_models) >= 2, (
        "yandexgpt must publish a non-empty list of supported model ids "
        "for the SetupWizard dropdown"
    )
    assert cat.default_model in cat.available_models, (
        "default_model must also appear in available_models — the wizard "
        "marks it as the suggested selection in the dropdown"
    )
    assert cat.needs_key is True
    assert cat.manual_setup is True
    assert cat.description


def test_catalog_default_model_is_in_available_models_for_every_provider(
    cls_param=None,
) -> None:
    """Invariant: every provider's default_model belongs to its own
    available_models. If the two drift apart the SetupWizard's
    dropdown would highlight a value it can't actually pick."""
    for cls in CONCRETE_PROVIDERS:
        cat = cls.catalog
        if not cat.default_model:
            # ``lm-studio`` has an empty default_model by design — the
            # operator's LM Studio UI serves whatever model it has
            # loaded, we don't pin one.
            assert cls is LMStudioLLM, (
                f"{cls.__name__} has empty default_model but isn't the "
                "lm-studio exemption — fix the catalog entry."
            )
            continue
        assert cat.default_model in cat.available_models, (
            f"{cls.__name__}: default_model={cat.default_model!r} not in "
            f"available_models={cat.available_models!r}"
        )


def test_provider_factory_uses_catalog_defaults_not_registry() -> None:
    """``ProviderLLM.__init__`` reads defaults from the subclass's catalog,
    not from ``api.constants.PROVIDERS[<id>]``. This is the regression
    guard for the move-from-registry refactor."""
    from types import SimpleNamespace

    from app.infrastructure.llm.factory import make_llm

    # Build a Settings-shaped namespace monkey-patched so the factory
    # sees the bare minimum (provider id + llm_api_key).
    secret = SimpleNamespace(get_secret_value=lambda: "sk-test")
    settings = SimpleNamespace(
        llm_provider="yandexgpt",
        llm_api_key=secret,
        chat_model="ignored",
        fast_model="ignored",
        llm_base_url="",
        app_referer="http://localhost:1420",
        default_temperature=0.7,
        default_max_tokens=4096,
        reasoning_field_names=["reasoning_content"],
    )
    llm = make_llm(settings)
    assert llm.base_url == yandexgpt_catalog.default_base_url
    assert llm.model == yandexgpt_catalog.default_model


def test_factory_overrides_still_win_over_catalog_defaults() -> None:
    """The operator may pin a specific model via Settings.llm_api_key-
    style overrides (e.g. ``chat_model=foo`` in ``.env``). Even with
    catalog-driven defaults the explicit override still wins."""
    from types import SimpleNamespace

    from app.infrastructure.llm.factory import make_llm

    secret = SimpleNamespace(get_secret_value=lambda: "sk-test")
    settings = SimpleNamespace(
        llm_provider="yandexgpt",
        llm_api_key=secret,
        chat_model="ignored",
        fast_model="ignored",
        llm_base_url="",
        app_referer="http://localhost:1420",
        default_temperature=0.7,
        default_max_tokens=4096,
        reasoning_field_names=["reasoning_content"],
    )
    llm = make_llm(settings, model_override="yandexgpt-lite/latest")
    assert llm.model == "yandexgpt-lite/latest"
    assert "yandexgpt-lite/latest" in yandexgpt_catalog.available_models
