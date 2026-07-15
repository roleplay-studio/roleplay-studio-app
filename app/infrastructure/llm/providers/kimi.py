"""Provider: Kimi (Moonshot AI — api.moonshot.cn).

Endpoint: ``https://api.moonshot.cn/v1``. Moonshot's ``moonshot-v1``
generation ships OpenAI-compatible chat-completions. The 8k /
32k / 128k variants are context-length siblings.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="kimi",
    label="Kimi (Moonshot)",
    description="Moonshot AI Kimi models",
    default_base_url="https://api.moonshot.cn/v1",
    default_model="moonshot-v1-8k",
    # The three context-length tiers Moonshot ships. 128k is the
    # flagship; 32k is the everyday workhorse; 8k is the cheap tier.
    available_models=(
        "moonshot-v1-8k",
        "moonshot-v1-32k",
        "moonshot-v1-128k",
    ),
    needs_key=True,
    manual_setup=False,
)


class KimiLLM(ProviderLLM):
    provider_id = "kimi"
    catalog = catalog
