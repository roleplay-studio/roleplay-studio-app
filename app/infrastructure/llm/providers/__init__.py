"""Per-provider LLM subclasses.

Each module is a thin subclass of :class:`ProviderLLM` which itself
inherits from :class:`app.infrastructure.llm.base_openai.BaseOpenAICompatibleLLM`.
Subclasses add no behaviour — they only set ``provider_id`` so the
base can pull defaults from ``api.constants.PROVIDERS``.

Public surface (consumed by the bootstrap factory in Phase 3):

* :class:`OpenRouterLLM` — hand-written subclass with hard-coded
  default_base_url (deployed first, Phase 1.3).
* :class:`OpenAILLM`, :class:`LMStudioLLM`, :class:`DeepSeekLLM`,
  :class:`GigaChatLLM`, :class:`GrokLLM`, :class:`KimiLLM`,
  :class:`MiniMaxLLM`, :class:`YandexGPTLLM`, :class:`ZAILLM` —
  registry-driven subclasses (Phase 2).
"""

from __future__ import annotations

from app.infrastructure.llm.providers._provider_llm import ProviderLLM
from app.infrastructure.llm.providers.deepseek import DeepSeekLLM
from app.infrastructure.llm.providers.gigachat import GigaChatLLM
from app.infrastructure.llm.providers.grok import GrokLLM
from app.infrastructure.llm.providers.kimi import KimiLLM
from app.infrastructure.llm.providers.lm_studio import LMStudioLLM
from app.infrastructure.llm.providers.minimax import MiniMaxLLM
from app.infrastructure.llm.providers.openai import OpenAILLM
from app.infrastructure.llm.providers.openrouter import OpenRouterLLM
from app.infrastructure.llm.providers.yandexgpt import YandexGPTLLM
from app.infrastructure.llm.providers.z_ai import ZAILLM

__all__ = [
    "ZAILLM",
    "DeepSeekLLM",
    "GigaChatLLM",
    "GrokLLM",
    "KimiLLM",
    "LMStudioLLM",
    "MiniMaxLLM",
    "OpenAILLM",
    "OpenRouterLLM",
    "ProviderLLM",
    "YandexGPTLLM",
]
