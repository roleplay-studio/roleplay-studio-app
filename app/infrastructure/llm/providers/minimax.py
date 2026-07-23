"""Provider: MiniMax (api.minimax.io).

Endpoint: ``https://api.minimax.io/v1`` — MiniMax hosts OpenAI-
compatible chat-completions. ``MiniMax-M3`` is the current
flagship; ``MiniMax-M2.5`` is the previous generation kept
around for compatibility.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="minimax",
    label="MiniMax",
    description="MiniMax chat & vision models",
    default_base_url="https://api.minimax.io/v1",
    default_model="MiniMax-M3",
    available_models=(
        "MiniMax-M3",
        "MiniMax-M2.5",
    ),
    needs_key=True,
    manual_setup=False,
)


class MiniMaxLLM(ProviderLLM):
    provider_id = "minimax"
    catalog = catalog
