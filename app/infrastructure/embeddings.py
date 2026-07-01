"""Custom HTTP embeddings client for OpenAI-compatible APIs.

Works with OpenRouter, LM Studio, Ollama, and any OpenAI-compatible
embeddings endpoint. Avoids incompatibilities with langchain's OpenAIEmbeddings
that some providers (e.g. LM Studio with bge-m3) don't handle.
"""

import httpx

from app.infrastructure.config import Settings


class HttpEmbeddings:
    """Minimal embeddings client that speaks OpenAI-compatible HTTP.

    Supports: OpenRouter, LM Studio, Ollama, vLLM, any OpenAI-compatible API.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = httpx.Client(timeout=30.0)

    @property
    def model(self) -> str | None:
        m = self._settings.embedding_model
        return m if m and m.strip() else None

    def _get_headers(self) -> dict[str, str]:
        """Return request headers.

        ``embedding_api_key`` is the *raw* value from the env (or
        ``Settings(openrouter_api_key=..., embedding_api_key=None)``
        in tests). HttpEmbeddings is intentionally dumb: it does NOT
        fall back to ``openrouter_api_key`` on its own — that
        decision lives in the embedding bootstrap path, where an
        unset embedding key means "use the openrouter key" but an
        explicit ``None`` means "no auth" (e.g. local Ollama).
        """
        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        api_key = self._settings.embedding_api_key
        if api_key is not None:
            # m15: SecretStr requires explicit unwrapping — this is
            # the single point where the value leaves the settings
            # boundary on its way to the wire.
            headers["Authorization"] = f"Bearer {api_key.get_secret_value()}"
        return headers

    def _get_base_url(self) -> str:
        # M13: ``effective_embedding_base_url`` falls back to the
        # openrouter URL when ``EMBEDDING_BASE_URL`` is unset. The
        # raw field may legitimately be ``None`` in that case.
        return self._settings.effective_embedding_base_url.rstrip("/")

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings. Returns a list of embeddings."""
        resp = self._client.post(
            f"{self._get_base_url()}/embeddings",
            headers=self._get_headers(),
            json={
                "input": texts,
                "model": self.model,
            },
        )
        data = resp.json()
        # OpenRouter (and some providers) return HTTP 200 with error inside body
        if "error" in data:
            err = data["error"]
            msg = err.get("message", str(err))
            raise RuntimeError(f"Embeddings API returned an error (HTTP {resp.status_code}): {msg}")
        resp.raise_for_status()
        # Sort by index to preserve ordering
        sorted_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in sorted_data]

    def embed_query(self, text: str) -> list[float]:
        """Embed a single query string."""
        resp = self._client.post(
            f"{self._get_base_url()}/embeddings",
            headers=self._get_headers(),
            json={
                "input": text,
                "model": self.model,
            },
        )
        data = resp.json()
        if "error" in data:
            err = data["error"]
            msg = err.get("message", str(err))
            raise RuntimeError(f"Embeddings API returned an error (HTTP {resp.status_code}): {msg}")
        resp.raise_for_status()
        return data["data"][0]["embedding"]

    def close(self) -> None:
        self._client.close()

    def __del__(self) -> None:
        self.close()
