"""Provider: Grok (api.x.ai — x.AI's hosted models).

Endpoint: ``https://api.x.ai/v1``. OpenAI-compatible chat-completions;
``BaseOpenAICompatibleLLM`` talks to it natively. Reasoning models
expose their chain-of-thought under ``reasoning_content`` and work
through the same reasoning-field routing as DeepSeek.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="grok",
    label="Grok (x.AI)",
    description="x.AI Grok models",
    default_base_url="https://api.x.ai/v1",
    default_model="grok-2-latest",
    # ``grok-2-latest`` is the rolling alias for the current flagship;
    # ``grok-2`` pins to a specific snapshot.
    available_models=(
        "grok-2-latest",
        "grok-2",
        "grok-2-mini",
        "grok-vision-beta",
    ),
    needs_key=True,
    manual_setup=False,
)


class GrokLLM(ProviderLLM):
    provider_id = "grok"
    catalog = catalog
