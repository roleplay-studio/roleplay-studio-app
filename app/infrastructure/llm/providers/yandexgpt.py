"""Provider: YandexGPT (Yandex Cloud, IAM-token auth).

Endpoint: ``https://llm.api.cloud.yandex.net/foundationModels/v1``
Wire:    OpenAI-compatible chat-completions, but IAM-token auth is
         issued out-of-band (the user pastes an IAM token into the
         SetupWizard — see ``manual_setup=True`` flag).

Default model: ``yandexgpt/latest`` (rolling alias; resolves at
request time to the current generation — yandexgpt 3 / 4 / etc.).
Older ``yandexgpt-lite`` is kept in the dropdown for operators
who want cheaper completions.

To add or retire a model: edit ``available_models`` here. The
SetupWizard's dropdown reads this list directly — no central
registry to keep in sync.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="yandexgpt",
    label="YandexGPT",
    description="Yandex Cloud YandexGPT (IAM token required)",
    default_base_url="https://llm.api.cloud.yandex.net/foundationModels/v1",
    default_model="yandexgpt/latest",
    # Rolling ``latest`` alias plus the two shippable generations.
    # ``summarization`` specialises yandexgpt-lite for short
    # responses — useful for thread recaps / short_content jobs.
    available_models=(
        "yandexgpt/latest",
        "yandexgpt-lite/latest",
        "yandexgpt/summarization",
    ),
    needs_key=True,
    manual_setup=True,  # IAM-token paste, not a simple API key field
)


class YandexGPTLLM(ProviderLLM):
    provider_id = "yandexgpt"
    catalog = catalog
