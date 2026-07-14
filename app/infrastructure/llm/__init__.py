"""LLM infrastructure package.

Public surface for the rest of the app:

* :class:`BaseOpenAICompatibleLLM` — provider-agnostic HTTP client
  for any OpenAI-compatible chat-completions endpoint (OpenRouter,
  OpenAI, DeepSeek, Grok, Kimi, MiniMax, LM Studio, Z.AI, custom).
* :class:`OpenRouterLLM` — thin subclass that wires ``Base`` defaults
  to OpenRouter's URL + chat-model defaults. The historical location
  ``app.infrastructure.llm.OpenRouterLLM`` is re-exported here for
  backward compatibility with the ~30 call-sites that imported it by
  name before Phase 1 of the LLM-provider refactor.
* :class:`LLMChunk` — streaming chunk dataclass (content / reasoning /
  usage / debug_messages).

The legacy ``app/infrastructure/llm.py`` module was replaced by this
package during the Phase 1.3 cleanup.
"""

from app.infrastructure.llm.base_openai import (
    BaseOpenAICompatibleLLM,
    LLMChunk,
    _extract_usage,
    _parse_sse_line,
    _split_delta,
)
from app.infrastructure.llm.providers.openrouter import OpenRouterLLM
from app.infrastructure.llm_mock import MockLLM

__all__ = [
    "BaseOpenAICompatibleLLM",
    "LLMChunk",
    "MockLLM",
    "OpenRouterLLM",
    # Module-private helpers re-exported for the legacy ``app.infrastructure.llm``
    # public surface; tests / patches import them by name.
    "_extract_usage",
    "_parse_sse_line",
    "_split_delta",
]  # verbose re-export list — keep flat for greppability
