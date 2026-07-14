"""Provider: kimi — thin subclass of ProviderLLM.

Defaults live in api.constants.PROVIDERS["kimi"]; this file only
declares the provider_id. All transport / streaming / reasoning logic
is in BaseOpenAICompatibleLLM.
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import ProviderLLM


class KimiLLM(ProviderLLM):
    provider_id = "kimi"
