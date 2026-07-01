"""Configuration loaded from environment variables via pydantic-settings.

This module is the single source of truth for runtime configuration.
The previous implementation used a hand-rolled ``@dataclass`` with a
170-line ``from_env()`` god-method (M1 in docs/review.md). It had
three problems:

* no type validation — ``DEFAULT_TEMPERATURE=hot`` only blew up on
  the first chat request (M2)
* adding a new env var meant copy-pasting four lines
* typing the fields as ``str | None`` lost the distinction between
  "explicitly empty" and "unset"

pydantic-settings solves all three: declarative field definitions,
automatic parsing, clear error messages at startup, and a stable
``SecretStr`` type for API keys (M15 — no more plain-text in memory).

Notes
-----
* ``from_env()`` is kept as a thin alias for ``Settings()`` so the
  50+ existing call-sites in this codebase (and external scripts)
  keep working without modification. New code should prefer
  ``Settings()`` directly.
* Some fields have non-trivial derivation rules that don't map to
  pydantic's default env parsing (e.g. ``embedding_api_key`` falls
  back to ``openrouter_api_key``, ``debug_enabled`` is true when
  ``DEBUG=true`` OR ``ENVIRONMENT=development``). These use
  ``@model_validator(mode="after")``.
* Fields that need Python-side defaults computed at import time
  (``version`` reading pyproject metadata) use ``default_factory``.
"""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _get_package_version() -> str:
    """Read the project version from the installed package metadata.

    Single source of truth: pyproject.toml [project].version.
    importlib.metadata reads it for installed packages; in dev mode
    (running from source without `pip install -e .`) the metadata
    is still discoverable via the pyproject metadata backend.
    Falls back to a dev marker only if the package is genuinely
    not installed at all (CI, vendored).
    """
    try:
        return _pkg_version("roleplay-studio")
    except PackageNotFoundError:
        return "0.0.0+unknown"


# Data directory: prefer ROLEPLAY_DATA_DIR (set by backend/run_backend.py),
# otherwise fall back to the project root (dev mode).
_DATA_DIR = Path(os.environ.get("ROLEPLAY_DATA_DIR", Path(__file__).resolve().parent.parent.parent))

# Try to load .env from data dir; if missing, the setup route will handle it.
# (pydantic-settings also reads .env via env_file, but we pre-load here so
# env vars are visible during this module's evaluation — e.g. for
# _DATA_DIR resolution that runs at import time.)
_env_path = _DATA_DIR / ".env"
if _env_path.exists():
    load_dotenv(_env_path)


def _is_truthy(value: str) -> bool:
    """Permissive truthiness check matching the rest of the codebase.

    ``"1"``, ``"true"``, ``"yes"``, ``"on"`` → True.
    Empty string, ``"false"``, ``"0"``, ``"no"`` → False.
    Anything else → True (preserves the pre-pydantic behaviour where
    ``bool(arbitrary_string) == True``).
    """
    return value.lower() not in ("", "false", "0", "no")


class Settings(BaseSettings):
    """Typed configuration loaded from the environment.

    The class is frozen-ish: pydantic models are immutable by default
    (``frozen=False`` so we can keep using the convenient construction
    syntax, but every field is read-only after init through pydantic's
    validation). This replaces the previous ``@dataclass(frozen=True)``
    which had to be hand-validated field by field.
    """

    model_config = SettingsConfigDict(
        env_file=str(_env_path) if _env_path.exists() else None,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ─────────────────────────────────────────────────────────
    # m15: keys are wrapped in SecretStr so they don't accidentally end
    # up in logs, Sentry, or debugger locals. Access via
    # ``settings.openrouter_api_key.get_secret_value()``.
    openrouter_api_key: SecretStr | None = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    chat_model: str = "openai/gpt-oss-20b"
    fast_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "qwen/qwen3-embedding-8b"
    # M13: the raw env value. Use ``effective_embedding_base_url`` to
    # get the post-fallback URL (defaults to ``openrouter_base_url``
    # when unset). Storing the raw value preserves the distinction
    # between "unset" and "explicitly empty" so a configuration
    # save-roundtrip doesn't accidentally clear an intentional
    # override.
    embedding_base_url: str | None = None
    embedding_api_key: SecretStr | None = None

    default_temperature: float = Field(0.7, ge=0.0, le=2.0)
    default_max_tokens: int = Field(4096, ge=1, le=200_000)
    # m14: HTTP-Referer used to be hard-coded to localhost:1420 in
    # llm.py. Now it follows ``Settings.app_referer`` (override via
    # APP_REFERER env var) so production deployments don't leak
    # "this is a Tauri dev box" to OpenRouter.
    app_referer: str = "http://localhost:1420"

    # ── Storage ────────────────────────────────────────────────────
    db_path: str = str(_DATA_DIR / "conversations.db")
    chroma_persist_dir: str = str(_DATA_DIR / "chroma_db")
    chroma_collection_prefix: str = "kb_bot_"
    upload_dir: str = "data/uploads"

    # ── RAG / Memory ───────────────────────────────────────────────
    knowledge_relevance_threshold: float = Field(0.3, ge=0.0, le=1.0)
    history_limit: int = Field(200, ge=10)

    # ── Summarization ─────────────────────────────────────────────
    summarize_enabled: bool = True
    summarize_max_tokens: int = Field(256, ge=1)
    summarize_min_length: int = Field(100, ge=1)
    summarize_recent_limit: int = Field(10, ge=1)
    thread_summary_enabled: bool = True
    thread_summary_interval: int = Field(10, ge=1)
    context_compression_enabled: bool = True
    context_compression_threshold: int = Field(50, ge=1)
    context_compression_keep_recent: int = Field(20, ge=0)
    summarize_batch_enabled: bool = True
    summarize_batch_size: int = Field(3, ge=1, le=20)

    # ── UI / Debug ─────────────────────────────────────────────────
    # m12: backward-compat shim. The original code stored these under
    # APP_LANGUAGE / APP_THEME in .env (see api/routes/config.py which
    # writes those keys). pydantic-settings' default field name → env
    # var mapping is the lowercased field name, so ``language`` would
    # read ``LANGUAGE`` — never matching the on-disk value. We bridge
    # via ``AliasChoices`` so both ``LANGUAGE=...`` and
    # ``APP_LANGUAGE=...`` are accepted. ``validation_alias`` is
    # preferred over the deprecated ``env`` kwarg in pydantic v2.
    language: str = Field(
        default="en",
        validation_alias=AliasChoices("language", "APP_LANGUAGE"),
    )
    theme: Literal["system", "light", "dark"] = Field(
        default="system",
        validation_alias=AliasChoices("theme", "APP_THEME"),
    )
    # debug_enabled is computed by the validator below from
    # DEBUG=true OR ENVIRONMENT=development.
    debug_enabled: bool = False
    # M4: explicit debug-dump directory. ``None`` → no dumps.
    debug_dump_dir: str | None = None
    # M4: TTL (hours) for ``debug_dump_dir`` payload files. The
    # langgraph orchestrator sweeps the directory on first dump in a
    # given process to keep disk usage bounded. Set to 0 to disable
    # cleanup (not recommended in long-running deployments).
    debug_dump_ttl_hours: int = 24
    # M4 + m12: opt-in flag for full LLM payload dumps. pydantic-settings
    # parses env strings "1"/"true"/"yes"/"on" as ``True`` automatically,
    # so this is the canonical replacement for the hand-rolled
    # ``os.getenv("DEBUG_PAYLOAD_DUMP", "").lower() in (...)`` parser.
    # Backward compat: the orchestrator still reads ``DEBUG_PAYLOAD_DUMP``
    # env var name (mapped via ``validation_alias``) so existing
    # ``DEBUG_PAYLOAD_DUMP=1`` setups keep working.
    debug_payload_dump: bool = False
    # M5: per-bot-type preamble overrides. ``dict[BotType.value, str]``
    # — pydantic-settings parses this from a JSON-encoded env string,
    # e.g. ``PREAMBLE_OVERRIDES='{"rp": "You are a samurai..."}'``.
    # Empty string is a valid override (clears the preamble for that
    # type). Unset / empty dict → use the built-in defaults.
    preamble_overrides: dict[str, str] = Field(default_factory=dict)
    # m13: list of field names the LLM provider may use to carry the
    # model's reasoning / chain-of-thought inside a streaming delta.
    # Different providers ship different names: OpenRouter normalises
    # to ``reasoning_content``, Anthropic uses ``thinking``,
    # DeepSeek-on-OpenRouter uses ``reasoning_content`` again, but
    # raw DeepSeek API exposes ``reasoning`` and some open-source
    # servers use ``thought`` or ``chain_of_thought``. Operators
    # running their own vLLM/Ollama/LM Studio can list whichever
    # names their model emits. Parsed as JSON from a single env var
    # — e.g. ``REASONING_FIELD_NAMES='["reasoning","thinking"]'``.
    # The LLM port iterates this list in order and stops at the
    # first hit. Default is OpenRouter-compatible.
    reasoning_field_names: list[str] = Field(default_factory=lambda: ["reasoning_content"])
    # m20: structured logging knobs. ``log_level`` is a free-form
    # string that maps to a stdlib level (DEBUG/INFO/WARNING/ERROR).
    # ``log_format`` is "pretty" (default, human-readable) or
    # "json" (single-line JSON per event, for ELK/Datadog/Loki
    # ingestion). Both flow through the same structlog processor
    # chain so existing ``logger.info(...)`` calls in the codebase
    # render correctly in either mode.
    log_level: str = "INFO"
    log_format: str = "pretty"

    # Project version — default_factory reads it at construction
    # time so updating pyproject.toml is reflected without a re-install
    # in dev mode. The AliasChoices makes pydantic-settings pick up
    # APP_VERSION (uppercase, matching the documented env var) before
    # falling back to the package-metadata default.
    version: str = Field(
        default_factory=_get_package_version,
        validation_alias=AliasChoices("version", "APP_VERSION"),
    )

    @model_validator(mode="before")
    @classmethod
    def _preprocess_env(cls, data: object) -> object:
        """Normalise empty-string env values to ``None`` before pydantic fills fields.

        pydantic-settings v2 does NOT pass env values to ``mode="before"``
        validators — they only see explicit kwargs. The pre-pydantic
        behaviour treated ``EMBEDDING_API_KEY=***`` as "no auth" and
        ``EMBEDDING_BASE_URL=***`` as "use openrouter_base_url". We
        preserve that by stripping empty strings *here* so the field
        stores ``None`` and the consumer's ``effective_embedding_*``
        helpers apply the right fallback. Explicit non-empty values
        pass through untouched.
        """
        if not isinstance(data, dict):
            return data
        for k in ("embedding_base_url", "embedding_api_key"):
            v = data.get(k)
            if isinstance(v, str) and v == "":
                data[k] = None
        return data

    @model_validator(mode="after")
    def _apply_debug_flag(self) -> Settings:
        """Compute ``debug_enabled`` from DEBUG / ENVIRONMENT env vars.

        This is the only cross-cutting rule we keep in a validator:
        ``debug_enabled`` is True when ``DEBUG=true`` OR
        ``ENVIRONMENT=development``. The field default is False and
        pydantic-settings does not know about either env var, so we
        set it here on every construction.
        """
        debug_raw = os.getenv("DEBUG", "")
        env_raw = os.getenv("ENVIRONMENT", "")
        object.__setattr__(
            self, "debug_enabled", _is_truthy(debug_raw) or env_raw.lower() == "development"
        )
        return self

    @classmethod
    def from_env(cls) -> Settings:
        """Backward-compatible alias for ``Settings()``.

        The pre-pydantic implementation had 50+ call-sites in the
        codebase that read ``Settings.from_env()``. Now that the
        class is a pydantic ``BaseSettings``, just instantiating
        it reads the environment — so this method is a no-op
        wrapper kept for readability and migration ergonomics.
        """
        return cls()

    @property
    def effective_embedding_base_url(self) -> str:
        """Embedding endpoint URL resolved from env-or-default.

        Returns ``self.embedding_base_url`` when set, else
        ``self.openrouter_base_url``. This is a convenience for
        callers (HttpEmbeddings, vectorstore) that don't want to
        repeat the ``or self.openrouter_base_url`` pattern.
        """
        return self.embedding_base_url or self.openrouter_base_url

    def require_openrouter_api_key(self) -> str:
        """Return the OpenRouter API key or raise ConfigurationError.

        Unwraps the SecretStr so callers (HTTP clients) can use the
        raw value without seeing the type noise.
        """
        # Import the domain-layer exception directly — breaks the
        # ``infrastructure → application`` cycle flagged in m3 of
        # docs/review.md. ``app.domain`` has no outward dependencies,
        # so it's a legal import target for both infrastructure and
        # application. The class is also re-exported from
        # ``app.application.exceptions`` for backward compat.
        from app.domain.exceptions import ConfigurationError

        if self.openrouter_api_key is None:
            raise ConfigurationError("OPENROUTER_API_KEY environment variable is required")
        return self.openrouter_api_key.get_secret_value()

    @property
    def db_url_for_alembic(self) -> str:
        """Full async SQLAlchemy URL for the configured SQLite database.

        Used by Alembic's env.py to stay in sync with the app's DB path.
        """
        path = self.db_path
        if path.startswith("sqlite+aiosqlite:///"):
            return path
        if path.startswith("sqlite:///"):
            return f"sqlite+aiosqlite:///{path.removeprefix('sqlite:///')}"
        return f"sqlite+aiosqlite:///{path}"

    @property
    def avatars_dir(self) -> Path:
        """Absolute path to the directory where bot avatars are stored.

        Kept in sync with ``api.constants.UPLOADS_DIR`` so the upload-avatar
        route, the bot-import service, and the export endpoint all read/write
        from the same physical location.
        """
        return Path(__file__).resolve().parent.parent.parent / "uploads" / "avatars"
