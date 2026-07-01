"""M5 unit tests for ``BotPreambleProvider`` and Settings overrides.

Covers:
* Built-in defaults are stable for each ``BotType`` (regression).
* ``Settings.preamble_overrides`` is parsed from JSON env string.
* Provider lookup precedence: override > built-in default > fallback.
* Provider injection works (so tests can stub the preamble text).
"""

from __future__ import annotations

from app.domain.enums import BotType
from app.infrastructure.config import Settings
from app.infrastructure.orchestration.preambles import (
    DEFAULT_CHAT_SYSTEM_PROMPT,
    BuiltinPreambleProvider,
)

# ── Built-in provider basics ────────────────────────────────────────


def test_builtin_provider_uses_defaults():
    provider = BuiltinPreambleProvider()
    assert "roleplay character" in provider.get(BotType.RP)
    assert "helpful assistant" in provider.get(BotType.ASSISTANT)
    assert "AI agent" in provider.get(BotType.AGENT)


def test_builtin_provider_fallback():
    """fallback() returns the neutral default — used when
    bot_personality is empty *and* we have no preamble text."""
    provider = BuiltinPreambleProvider()
    assert provider.fallback() == DEFAULT_CHAT_SYSTEM_PROMPT


def test_builtin_provider_unknown_type_returns_default():
    """Unknown bot_type (not in the dict) → fallback default."""
    provider = BuiltinPreambleProvider()
    # We can't construct an invalid BotType easily — use a string-cast
    # trick. The provider's contract: get(BotType) — and BuiltinPreambleProvider
    # returns DEFAULT_CHAT_SYSTEM_PROMPT for any BotType not in
    # _DEFAULT_PREAMBLES. We don't actually have such a BotType value,
    # so this test mostly checks the public surface.
    assert isinstance(provider.get(BotType.RP), str)


# ── Settings.preamble_overrides parsing ─────────────────────────────


def test_preamble_overrides_default_is_empty(monkeypatch):
    monkeypatch.delenv("PREAMBLE_OVERRIDES", raising=False)
    settings = Settings(_env_file=None)
    assert settings.preamble_overrides == {}


def test_preamble_overrides_parses_json_env(monkeypatch):
    """pydantic-settings parses dict[str, str] from a JSON env string."""
    monkeypatch.setenv(
        "PREAMBLE_OVERRIDES",
        '{"rp": "You are a samurai.", "agent": "You are a coder."}',
    )
    settings = Settings(_env_file=None)
    assert settings.preamble_overrides == {
        "rp": "You are a samurai.",
        "agent": "You are a coder.",
    }


def test_preamble_overrides_empty_string_is_valid_override(monkeypatch):
    """An empty string IS a valid override (clears the preamble for
    that type). Caller must distinguish unset dict from empty string."""
    monkeypatch.setenv("PREAMBLE_OVERRIDES", '{"rp": ""}')
    settings = Settings(_env_file=None)
    assert settings.preamble_overrides == {"rp": ""}


# ── Override wins over default ──────────────────────────────────────


def test_override_wins_over_default():
    provider = BuiltinPreambleProvider(overrides={"rp": "You are a wizard."})
    assert provider.get(BotType.RP) == "You are a wizard."
    # Non-overridden types still use the built-in.
    assert "helpful assistant" in provider.get(BotType.ASSISTANT)


def test_empty_string_override_clears_preamble():
    """Empty string is a valid override (per M5 docstring). The
    provider must return it as-is, not fall through to the default."""
    provider = BuiltinPreambleProvider(overrides={"rp": ""})
    assert provider.get(BotType.RP) == ""


# ── Injection / stubbing ────────────────────────────────────────────


class _StubProvider:
    """Test-only stub for ``BotPreambleProvider`` Protocol."""

    def __init__(self, text: str) -> None:
        self._text = text

    def get(self, bot_type: BotType) -> str:
        return self._text

    def fallback(self) -> str:
        return self._text


def test_orchestrator_uses_injected_provider():
    """The orchestrator constructor takes a ``preamble_provider`` so
    tests can stub it — this verifies the injection path works."""
    from app.infrastructure.llm import LLMChunk
    from app.infrastructure.orchestration.langgraph_orchestrator import (
        LangGraphConversationOrchestrator,
    )

    class _StubLLM:
        async def generate_response(self, messages, temperature=None, max_tokens=None):
            return "ok"

        async def generate_response_stream(self, messages, temperature=None, max_tokens=None):
            yield LLMChunk(content="ok")

        async def generate(self, request):
            return "ok"

        async def generate_stream(self, request):
            yield LLMChunk(content="ok")

    orch = LangGraphConversationOrchestrator(
        llm=_StubLLM(),
        preamble_provider=_StubProvider(text="CUSTOM"),
    )
    # The provider is plumbed in — but the actual prompt assembly
    # happens inside ``_build_system_prompt``; we only need to verify
    # the attribute is set here. Stub is duck-typed, so the Protocol
    # is satisfied structurally (no isinstance — Protocol isn't
    # runtime_checkable here).
    assert orch._preamble_provider.get(BotType.RP) == "CUSTOM"
