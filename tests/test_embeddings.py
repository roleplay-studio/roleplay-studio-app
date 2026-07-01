"""Tests for HttpEmbeddings configuration resolution."""

from app.infrastructure.config import Settings
from app.infrastructure.embeddings import HttpEmbeddings


def test_http_embeddings_uses_embedding_base_url():
    settings = Settings(
        openrouter_base_url="https://openrouter.ai/api/v1",
        embedding_base_url="http://localhost:11434/v1",
        embedding_api_key=None,
    )
    emb = HttpEmbeddings(settings)
    assert emb._get_base_url() == "http://localhost:11434/v1"


def test_http_embeddings_uses_embedding_api_key_when_set():
    settings = Settings(
        openrouter_api_key="sk-or-ignored",
        embedding_api_key="sk-local",
    )
    emb = HttpEmbeddings(settings)
    assert emb._get_headers()["Authorization"] == "Bearer sk-local"


def test_http_embeddings_omits_auth_when_no_key():
    settings = Settings(
        openrouter_api_key=None,
        embedding_api_key=None,
    )
    emb = HttpEmbeddings(settings)
    assert "Authorization" not in emb._get_headers()


def test_http_embeddings_does_not_fall_back_to_openrouter_api_key():
    """Critical: HttpEmbeddings no longer falls back to openrouter_api_key.
    Settings.from_env has already resolved the value (None for no-auth,
    or the openrouter key for unset/embed_key). HttpEmbeddings is dumb.
    """
    settings = Settings(
        openrouter_api_key="sk-or-test",
        embedding_api_key=None,  # explicit no-auth (e.g. Ollama)
    )
    emb = HttpEmbeddings(settings)
    assert "Authorization" not in emb._get_headers()
