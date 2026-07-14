"""Per-provider LLM subclasses.

Each module is a thin subclass of ``BaseOpenAICompatibleLLM`` (or,
eventually, ``BaseAnthropicLLM`` once populated). Subclasses supply
provider-specific metadata only — default ``base_url``, default chat
``model``, optional auth-header tweaks. All transport / streaming /
reasoning / usage logic lives in the base class.

Phase 1 of the LLM-provider refactor only ships ``openrouter``; the
remaining eight OpenAI-compatible providers (openai / lm-studio /
deepseek / gigachat / grok / kimi / minimax / yandexgpt / z-ai) are
added in Phase 2.
"""
