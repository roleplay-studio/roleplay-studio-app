"""Validate that an embedding endpoint is reachable and accepts a test request."""

import httpx

from app.domain.exceptions import ConfigurationError


def validate_embedding_endpoint(base_url: str, api_key: str | None, model: str) -> None:
    """POST a 1-token test embedding to verify the endpoint works.

    Raises ConfigurationError with a human-readable message on failure.
    Uses POST /embeddings (not GET /models) because Ollama does not expose
    /models in OpenAI format.
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        resp = httpx.post(
            f"{base_url.rstrip('/')}/embeddings",
            headers=headers,
            json={"input": "test", "model": model},
            timeout=15.0,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise ConfigurationError("Authentication failed. Check your API key.") from e
        if e.response.status_code == 404:
            raise ConfigurationError(f"Model '{model}' not found on this endpoint.") from e
        raise ConfigurationError(f"Embedding endpoint returned {e.response.status_code}.") from e
    except httpx.ConnectError as e:
        raise ConfigurationError(
            f"Cannot reach embedding endpoint at {base_url}. "
            "Is the server running? (Ollama: ollama serve; "
            "LM Studio: enable the local server in the UI.)"
        ) from e
    except httpx.TimeoutException as e:
        raise ConfigurationError(f"Embedding endpoint timed out at {base_url}.") from e
