"""Provider: DeepSeek (api.deepseek.com).

Endpoint: ``https://api.deepseek.com/v1`` — DeepSeek ships an
OpenAI-compatible chat-completions endpoint. Reasoning models
(streaming ``reasoning_content`` field) work natively through
``BaseOpenAICompatibleLLM``'s configurable reasoning-field support.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="deepseek",
    label="DeepSeek",
    description="DeepSeek chat & reasoning models",
    default_base_url="https://api.deepseek.com/v1",
    default_model="deepseek-chat",
    # ``deepseek-chat`` is the all-rounder; ``deepseek-reasoner`` is
    # the o1-style chain-of-thought model whose ``reasoning_content``
    # stream field needs to be filtered out of the user-visible reply.
    available_models=(
        "deepseek-chat",
        "deepseek-reasoner",
    ),
    needs_key=True,
    manual_setup=False,
)


class DeepSeekLLM(ProviderLLM):
    provider_id = "deepseek"
    catalog = catalog
