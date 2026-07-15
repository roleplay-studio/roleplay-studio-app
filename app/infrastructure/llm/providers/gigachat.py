"""Provider: GigaChat (Sberbank, OAuth auth).

Endpoint: ``https://gigachat.devices.sberbank.ru/api/v1``. GigaChat
uses OAuth tokens (not API keys), issued through a separate
handshake — see ``manual_setup=True``. The OpenAI-compatible wire
protocol includes a few GigaChat-specific request fields
(``profanity_check``, ``verbose_responses``) that the base class
ignores today; enabling them would be a ``_build_body`` override
here.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import (
    ProviderCatalog,
    ProviderLLM,
)

catalog = ProviderCatalog(
    provider_id="gigachat",
    label="GigaChat",
    description="Sberbank GigaChat (OAuth required)",
    default_base_url="https://gigachat.devices.sberbank.ru/api/v1",
    default_model="GigaChat",
    # The two flagship GigaChat generations as of late 2024. Lite is
    # the cheaper 7B variant, Pro the full 29B model. Embeddings use
    # a separate endpoint and aren't selectable through the chat
    # provider's model list.
    available_models=("GigaChat", "GigaChat-Pro"),
    needs_key=True,
    manual_setup=True,
)


class GigaChatLLM(ProviderLLM):
    provider_id = "gigachat"
    catalog = catalog
