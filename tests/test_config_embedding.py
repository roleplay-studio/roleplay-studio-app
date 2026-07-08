"""Tests for embedding endpoint settings resolution."""

from app.infrastructure.config import Settings


def test_settings_from_env_uses_llm_default_for_embedding_base_url(monkeypatch):
    """Unset EMBEDDING_BASE_URL → falls back to LLM_BASE_URL.

    After the M1+M13 refactor (pydantic-settings), the cross-field
    fallback lives in ``Settings.effective_embedding_base_url`` —
    the raw ``embedding_base_url`` field is left as ``None`` so a
    save-roundtrip can persist "unset" without losing an explicit
    override later. Passes ``_env_file=None`` so the local on-disk
    .env doesn't shadow the monkeypatched environment.
    """
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.delenv("EMBEDDING_BASE_URL", raising=False)
    s = Settings(_env_file=None)
    assert s.effective_embedding_base_url == "https://openrouter.ai/api/v1"


def test_settings_from_env_overrides_embedding_base_url(monkeypatch):
    monkeypatch.setenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("EMBEDDING_BASE_URL", "http://localhost:11434/v1")
    s = Settings(_env_file=None)
    assert s.embedding_base_url == "http://localhost:11434/v1"
    assert s.effective_embedding_base_url == "http://localhost:11434/v1"


def test_settings_from_env_embedding_api_key_unset_stays_none(monkeypatch):
    """Unset EMBEDDING_API_KEY → embedding_api_key remains None.

    After the M1+M15 refactor (pydantic-settings + SecretStr), the
    cross-field fallback no longer lives in Settings itself. The
    raw field stores ``None`` when unset; the consumer (e.g. the
    embedding bootstrap path) decides whether to fall back to
    ``llm_api_key``. This split is what lets the
    ``test_http_embeddings_does_not_fall_back_to_llm_api_key``
    test enforce "explicit None = no auth" semantics at the
    HttpEmbeddings layer.
    """
    monkeypatch.setenv("LLM_API_KEY", "sk-or-test")
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.embedding_api_key is None
    # The raw field stays None — fallback is the consumer's job.


def test_settings_from_env_embedding_api_key_empty_is_no_auth(monkeypatch):
    """EMBEDDING_API_KEY=*** → no auth (None), even if LLM_API_KEY is set."""
    monkeypatch.setenv("LLM_API_KEY", "sk-or-test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "")
    s = Settings(_env_file=None)
    assert s.embedding_api_key is None


def test_settings_from_env_embedding_api_key_explicit_value(monkeypatch):
    """EMBEDDING_API_KEY='***' → use that value, ignore llm."""
    monkeypatch.setenv("LLM_API_KEY", "sk-or-test")
    monkeypatch.setenv("EMBEDDING_API_KEY", "sk-local")
    s = Settings(_env_file=None)
    assert s.embedding_api_key is not None
    assert s.embedding_api_key.get_secret_value() == "sk-local"


def test_settings_from_env_embedding_api_key_unset_no_llm(monkeypatch):
    """Both unset → embedding_api_key is None."""
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("EMBEDDING_API_KEY", raising=False)
    s = Settings(_env_file=None)
    assert s.embedding_api_key is None
