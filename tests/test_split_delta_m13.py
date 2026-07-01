"""m13 unit tests — ``_split_delta`` reasoning field name fallback.

Covers the fix for m13 (docs/review.md): the previous implementation
hard-coded the OpenAI/DeepSeek ``reasoning_content`` field name. Some
providers ship different names:

* Anthropic Claude: ``thinking``
* Raw DeepSeek API: ``reasoning``
* LM Studio / Ollama: ``thought`` or ``chain_of_thought``
* OpenRouter: ``reasoning_content`` (default)

The fix: a list of candidate names, iterated in order; the first
one present in the delta wins. Configured via
``Settings.reasoning_field_names`` (env var REASONING_FIELD_NAMES,
JSON-encoded list). Default keeps the OpenRouter behaviour.
"""

from __future__ import annotations

from app.infrastructure.llm import _split_delta

# ── Default (OpenRouter) behaviour ──────────────────────────────────


def test_default_uses_reasoning_content():
    """The default field list is ``["reasoning_content"]`` —
    matches OpenRouter and the historical single-name behaviour."""
    content, reasoning = _split_delta({"content": "hi", "reasoning_content": "thinking..."})
    assert content == "hi"
    assert reasoning == "thinking..."


def test_default_no_reasoning_returns_none():
    """A delta without any reasoning field (most non-reasoning
    models) returns ``None`` — not the empty string."""
    content, reasoning = _split_delta({"content": "hi"})
    assert content == "hi"
    assert reasoning is None


def test_default_empty_reasoning_preserves_empty_string():
    """An explicitly-empty reasoning field (model signals "end of
    reasoning" with ``""``) is preserved as ``""`` — not coerced
    to ``None``. This is the pre-m13 behaviour and several
    downstream tests rely on it."""
    content, reasoning = _split_delta({"content": "hi", "reasoning_content": ""})
    assert content == "hi"
    assert reasoning == ""


# ── Custom field names ─────────────────────────────────────────────


def test_anthropic_thinking_field():
    """Anthropic emits ``thinking`` instead of ``reasoning_content``.
    Operators running raw Anthropic can set
    REASONING_FIELD_NAMES='["thinking"]' to pick it up."""
    content, reasoning = _split_delta(
        {"content": "hi", "thinking": "considering..."},
        reasoning_field_names=["thinking"],
    )
    assert content == "hi"
    assert reasoning == "considering..."


def test_multiple_candidate_names_first_wins():
    """When the delta carries multiple reasoning-style fields
    (rare, but happens with vLLM proxies that pass through
    upstream metadata), the first name in the list wins."""
    _content, reasoning = _split_delta(
        {
            "content": "hi",
            "reasoning": "raw api version",
            "reasoning_content": "openrouter normalised",
        },
        reasoning_field_names=["reasoning", "reasoning_content"],
    )
    assert reasoning == "raw api version"


def test_multiple_candidate_names_falls_back():
    """When the first candidate is missing, fall through to the
    second. This is the vLLM/Ollama use case where a custom
    model emits ``thought`` and we want a safety net for
    ``reasoning_content`` (in case the same model is also
    proxied via OpenRouter)."""
    _content, reasoning = _split_delta(
        {"content": "hi", "reasoning_content": "fallback value"},
        reasoning_field_names=["thought", "reasoning_content"],
    )
    assert reasoning == "fallback value"


def test_no_candidate_matches_returns_none():
    """When none of the configured field names are present in the
    delta (the common case for non-reasoning models), return None."""
    content, reasoning = _split_delta(
        {"content": "hi", "unrelated_field": "x"},
        reasoning_field_names=["reasoning", "thinking"],
    )
    assert content == "hi"
    assert reasoning is None


# ── Content vs reasoning separation (regression) ───────────────────


def test_content_does_not_fall_back_to_reasoning():
    """The CRITICAL pre-existing invariant: an empty ``content``
    must NOT pull from the reasoning field. This is the
    security/leakage check — if the model emits
    ``{"content": "", "reasoning_content": "internal thoughts"}``,
    we must return ``("", "internal thoughts")``, NOT
    ``("internal thoughts", None)``."""
    content, reasoning = _split_delta({"content": "", "reasoning_content": "internal thoughts"})
    assert content == ""
    assert reasoning == "internal thoughts"
    # The two are now in separate fields — the frontend can render
    # them independently. Pre-fix, the ``or``-based extraction
    # would have returned ``("internal thoughts", None)``,
    # leaking chain-of-thought to the user.
