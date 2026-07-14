"""Provider: Z.AI / Zhipu GLM (api.z.ai).

Endpoint: ``https://api.z.ai/v1``. Zhipu's GLM-4 generation
ships OpenAI-compatible chat-completions.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="z-ai",
    label="Z.AI (GLM)",
    description="Zhipu AI GLM models",
    default_base_url="https://api.z.ai/v1",
    default_model="glm-4.6",
    # The GLM-4 generation as of late 2024. ``glm-4-flash`` is the
    # cheap/free tier; ``glm-4-plus`` is the production flagship.
    available_models=(
        "glm-4.6",
        "glm-4-plus",
        "glm-4-air",
        "glm-4-flash",
    ),
    needs_key=True,
    manual_setup=False,
)


class ZAILLM(ProviderLLM):
    provider_id = "z-ai"
    catalog = catalog
