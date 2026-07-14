"""Provider: MiniMax (api.minimaxi.com).

Endpoint: ``https://api.minimaxi.com/v1`` — MiniMax hosts OpenAI-
compatible chat-completions. ``MiniMax-Text-01`` is the text-only
flagship; ``abab`` series are the older-generation models kept
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
    default_base_url="https://api.minimaxi.com/v1",
    default_model="MiniMax-Text-01",
    available_models=(
        "MiniMax-Text-01",
        "abab6.5s-chat",
        "abab6.5-chat",
        "abab5.5-chat",
    ),
    needs_key=True,
    manual_setup=False,
)


class MiniMaxLLM(ProviderLLM):
    provider_id = "minimax"
    catalog = catalog
