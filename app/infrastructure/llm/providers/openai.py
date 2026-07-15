"""Provider: OpenAI (api.openai.com).

Endpoint: ``https://api.openai.com/v1`` — OpenAI's own chat-completions
endpoint, which ``BaseOpenAICompatibleLLM`` talks to natively.

Note: this is the same wire protocol we use for every OpenAI-compatible
provider. The only thing that distinguishes the providers here is the
default URL and the model list.

To add or retire a model: edit ``available_models``.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="openai",
    label="OpenAI",
    description="Official OpenAI API",
    default_base_url="https://api.openai.com/v1",
    default_model="gpt-4o-mini",
    # Stable identifiers as of late 2024. The cheapest usable flagship
    # is gpt-4o-mini. gpt-4o / gpt-4-turbo are quality/price options.
    available_models=(
        "gpt-4o-mini",
        "gpt-4o",
        "gpt-4-turbo",
        "o1-mini",
    ),
    needs_key=True,
    manual_setup=False,
)


class OpenAILLM(ProviderLLM):
    provider_id = "openai"
    catalog = catalog
