"""Tests for embedding endpoint validation."""

import httpx
import pytest

from app.application.exceptions import ConfigurationError
from app.infrastructure.embedding_validation import validate_embedding_endpoint


def test_validate_endpoint_succeeds_on_200(monkeypatch):
    """Mocked POST /embeddings returning 200 → no error raised."""

    def mock_post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"data": [{"embedding": [0.1, 0.2]}]}, request=request)

    monkeypatch.setattr(httpx, "post", mock_post)
    # Should not raise
    validate_embedding_endpoint("http://localhost:11434/v1", None, "bge-m3")


def test_validate_endpoint_fails_on_401(monkeypatch):
    """Mocked 401 → ConfigurationError mentioning auth."""

    def mock_post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(401, json={"error": "unauthorized"}, request=request)

    monkeypatch.setattr(httpx, "post", mock_post)
    with pytest.raises(ConfigurationError, match=r"[Aa]uthentication"):
        validate_embedding_endpoint("http://localhost:11434/v1", "sk-bad", "bge-m3")


def test_validate_endpoint_fails_on_404(monkeypatch):
    """Mocked 404 → ConfigurationError mentioning model."""

    def mock_post(url, **kwargs):
        request = httpx.Request("POST", url)
        return httpx.Response(404, json={"error": "not found"}, request=request)

    monkeypatch.setattr(httpx, "post", mock_post)
    with pytest.raises(ConfigurationError, match=r"[Mm]odel"):
        validate_embedding_endpoint("http://localhost:11434/v1", None, "does-not-exist")


def test_validate_endpoint_fails_on_connect_error(monkeypatch):
    """ConnectError → ConfigurationError mentioning reachability."""

    def mock_post(url, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", mock_post)
    with pytest.raises(ConfigurationError, match=r"[Cc]annot reach"):
        validate_embedding_endpoint("http://localhost:9999/v1", None, "bge-m3")


def test_validate_endpoint_includes_bearer_when_key_provided(monkeypatch):
    """POST should include Authorization: Bearer *** when key is set."""
    captured = {}

    def mock_post(url, **kwargs):
        captured.update(kwargs.get("headers", {}))
        request = httpx.Request("POST", url)
        return httpx.Response(200, json={"data": [{"embedding": [0.1]}]}, request=request)

    monkeypatch.setattr(httpx, "post", mock_post)
    validate_embedding_endpoint("http://localhost:11434/v1", "sk-test", "bge-m3")
    assert captured.get("Authorization") == "Bearer sk-test"
