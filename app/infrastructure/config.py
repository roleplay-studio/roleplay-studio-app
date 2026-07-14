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
  back to ``llm_api_key``, ``debug_enabled`` is true when
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
from pydantic import AliasChoices, Field, SecretStr, field_validator, model_validator
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
    # The default provider is OpenRouter, but the same key/URL pair
    # works against any OpenAI-compatible endpoint (LM Studio, Ollama,
    # vLLM, …). Field names therefore stay generic.
    #
    # m15: keys are wrapped in SecretStr so they don't accidentally end
    # up in logs, Sentry, or debugger locals. Access via
    # ``settings.llm_api_key.get_secret_value()``.
    llm_api_key: SecretStr | None = None
    llm_base_url: str = "https://openrouter.ai/api/v1"
    # M16+: ``llm_provider`` selects which LLM implementation
    # ``app.bootstrap.build_container`` wires into the application.
    # Valid values: ``"mock"`` (deterministic simulator for E2E / CI)
    # plus any id registered in ``api.constants.PROVIDERS`` (openrouter,
    # openai, lm-studio, deepseek, gigachat, grok, kimi, minimax,
    # yandexgpt, z-ai, custom). Unknown values fall back to ``"mock"``
    # with a ``logger.warning`` — mirrors the silent fallback in
    # ``bootstrap.build_container`` before this refactor. The validator
    # below is the single source of truth for valid ids; ``PROVIDERS``
    # in ``api/constants.py`` remains the canonical metadata registry
    # shared with ``/api/setup/providers``.
    llm_provider: str = "openrouter"
    chat_model: str = "openai/gpt-oss-20b"
    fast_model: str = "openai/gpt-4o-mini"
    embedding_model: str = "qwen/qwen3-embedding-8b"
    # M13: the raw env value. Use ``effective_embedding_base_url`` to
    # get the post-fallback URL (defaults to ``llm_base_url``
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
    # The default values are bare filenames / folder names. The
    # *effective* path (absolute, with ``ROLEPLAY_DATA_DIR`` resolved
    # for relative values) is exposed via the ``data_dir`` and
    # ``effective_*`` properties below. This split lets the Settings
    # page show the user a clean, round-trippable value
    # (e.g. ``conversations.db``) while runtime code keeps working
    # with a full filesystem path.
    db_path: str = "conversations.db"
    chroma_persist_dir: str = "chroma_db"
    chroma_collection_prefix: str = "kb_bot_"
    upload_dir: str = "uploads"

    # ── RAG / Memory ───────────────────────────────────────────────
    knowledge_relevance_threshold: float = Field(0.3, ge=0.0, le=1.0)
    # Maximum messages loaded from the DB for the LLM context.
    # Raised from 200 to 1000 so DEBUG1-class threads (>200 messages)
    # don't silently drop history before context compression even
    # gets a chance to run. ``_load_full_history`` logs a warning
    # when the DB actually holds more rows than this cap, so users
    # that hit the limit again can raise it from Settings instead
    # of wondering "where did my old messages go".
    history_limit: int = Field(1000, ge=10)

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

    # ── State context ─────────────────────────────────────────────
    # Number of recent user/assistant pairs the state-generation
    # LLM sees alongside the previous state snapshot. The default
    # (10 pairs) is chosen to match SUMMARIZE_RECENT_LIMIT so the
    # 'recent' window has the same ceiling everywhere. Without
    # this, ``regenerate_state`` only sees the previous state plus
    # the current exchange — anything between the last successful
    # state regen and now is lost, so the regenerator must guess.
    # Set to 0 to restore the legacy minimal prompt (only current
    # user + assistant + previous state).
    state_context_pairs: int = Field(10, ge=0)

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
    # Optional file sink for structured logs. When set, every event
    # also lands in this file in the configured ``log_format`` (so
    # ``log_format="json"`` + ``log_file=...`` is the recommended
    # debug-bundle combo). Path is relative to ``ROLEPLAY_DATA_DIR``
    # unless absolute. Rotated at 10 MB x 3 to keep disk usage
    # bounded — a chat stream that crashes mid-run can otherwise
    # produce megabytes per request.
    log_file: str | None = None

    # ── TTS (text-to-speech) ───────────────────────────────────────
    # Operator-level switch. ``"minimax"`` hits
    # ``https://api.minimaxi.com/v1/t2a_v2``; ``"mock"`` swaps in an
    # in-process deterministic synthesizer (no API call, no cost) for
    # E2E suites and local dev; ``"disabled"`` (default) means the
    # frontend hides the play button entirely — TTS is opt-in.
    #
    # Key/auth: ``tts_api_key`` falls back to ``llm_api_key`` via the
    # validator below so users who already have a provider key don't
    # have to duplicate it. Base URL is overridable for proxying /
    # LM Studio TTS.
    tts_provider: Literal["disabled", "mock", "minimax"] = "disabled"
    tts_api_key: SecretStr | None = None
    tts_base_url: str = "https://api.minimaxi.com/v1"
    # MiniMax's published voice catalog uses ``<Language>_<Persona>``
    # strings (e.g. ``Russian_ReliableMan``, ``English_Graceful_Lady``,
    # ``German_SweetLady``). ``english_female_1`` is NOT a real id —
    # the default value was set when the integration was written
    # against an older catalog and silently returns HTTP 502 on first
    # use. ``Russian_ReliableMan`` is a safe documented default; the
    # Settings page exposes the full catalog so operators can pick.
    tts_voice_id: str = "Russian_ReliableMan"
    tts_model: str = "speech-02-turbo"
    tts_speed: float = Field(1.0, ge=0.5, le=2.0)
    # Where synthesised audio is cached on disk. Bare filename resolves
    # under ``data_dir`` so a relative ``tts_cache`` in .env lands in
    # ``$ROLEPLAY_DATA_DIR/tts_cache/`` — the same lifecycle as the
    # Chroma / uploads directories.
    tts_cache_dir: str = "tts_cache"

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
        ``EMBEDDING_BASE_URL=***`` as "use llm_base_url". We
        preserve that by stripping empty strings *here* so the field
        stores ``None`` and the consumer's ``effective_embedding_*``
        helpers apply the right fallback. Explicit non-empty values
        pass through untouched.
        """
        if not isinstance(data, dict):
            return data
        for k in ("embedding_base_url", "embedding_api_key", "tts_api_key"):
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

    @field_validator("llm_provider", mode="before")
    @classmethod
    def _validate_llm_provider(cls, v: object) -> str:
        """Validate ``llm_provider`` against ``api.constants.PROVIDERS + {'mock'}``.

        Unknown values (including a non-string leaking through env
        parsing) fall back to ``"mock"`` with a ``logger.warning``.

        Cycle-breaking dance: ``api/constants.py`` itself imports
        ``Settings`` at module level (``UPLOADS_DIR = ... Settings.from_env() ...``).
        If the first ever ``Settings()`` is triggered from inside
        ``api.constants`` module load, then ``api.constants`` is
        partially initialised and ``PROVIDERS`` isn't accessible yet.
        We work around that in two ways:

        1. ``mock`` is short-circuited before any import — it always
           validates without touching ``api.constants``.
        2. For real provider ids we first check ``sys.modules``; only
           fall back to a fresh import if the module is already fully
           loaded there. If the module is currently being initialised
           (cycle case), we treat the value as already validated
           against the known set — the import will complete correctly
           on every subsequent ``Settings()`` call once the cycle ends.
        """
        import logging
        import sys as _sys

        if not isinstance(v, str) or not v:
            v_norm = ""
        else:
            v_norm = v.strip().lower()
            if v_norm == "mock":
                return "mock"

        if v_norm == "":
            logging.getLogger(__name__).warning(
                "Settings.llm_provider is empty/non-string (%r); "
                "falling back to 'mock'",
                v,
            )
            return "mock"

        # If api.constants is already fully loaded, validate against its
        # PROVIDERS registry. Otherwise (cycle case) accept the value as
        # provisionally valid; the next Settings() call after the cycle
        # ends will re-validate against the real registry.
        api_constants = _sys.modules.get("api.constants")
        if api_constants is not None and hasattr(api_constants, "PROVIDERS"):
            if v_norm in api_constants.PROVIDERS:
                return v_norm
            logging.getLogger(__name__).warning(
                "Settings.llm_provider=%r is not a known provider id "
                "(known: %r, 'mock'); falling back to 'mock'",
                v,
                sorted(api_constants.PROVIDERS.keys()),
            )
            return "mock"
        # Cycle: api.constants partially initialised. Accept provisional
        # ids; full validation happens on the next non-cyclical call.
        return v_norm

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
        ``self.llm_base_url``. This is a convenience for
        callers (HttpEmbeddings, vectorstore) that don't want to
        repeat the ``or self.llm_base_url`` pattern.
        """
        return self.embedding_base_url or self.llm_base_url

    def require_llm_api_key(self) -> str:
        """Return the LLM API key or raise ConfigurationError.

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

        if self.llm_api_key is None:
            raise ConfigurationError("LLM_API_KEY environment variable is required")
        return self.llm_api_key.get_secret_value()

    @property
    def effective_tts_api_key(self) -> SecretStr | None:
        """TTS key with fallback to ``llm_api_key``.

        Mirrors ``effective_embedding_api_key`` — if the operator
        hasn't set ``TTS_API_KEY`` explicitly, we re-use the LLM key
        so users with one MiniMax key don't have to duplicate it.
        Returns ``None`` when neither is set (caller should bail —
        don't auto-create).
        """
        return self.tts_api_key if self.tts_api_key is not None else self.llm_api_key

    @property
    def effective_tts_cache_dir(self) -> Path:
        """Absolute TTS cache directory — bare names resolve under ``data_dir``.

        Separate property (not piggy-backed on ``_resolve``) so the
        TTS bootstrap code can read it without coupling to other
        cache dirs (Chroma / uploads).
        """
        return self._resolve(self.tts_cache_dir)

    @property
    def data_dir(self) -> Path:
        """Absolute data directory for runtime files.

        Resolved at access time so it picks up ``ROLEPLAY_DATA_DIR``
        changes that happen AFTER ``Settings`` is constructed — the
        bare default values in this class can't bake the data dir in
        at import time without freezing it to whatever was set when
        this module first loaded.

        In production ``backend/run_backend.py`` sets
        ``ROLEPLAY_DATA_DIR`` before importing ``app.*`` so this
        returns the same value the legacy module-level ``_DATA_DIR``
        would have computed. In dev the project root is the fallback.
        """
        return Path(
            os.environ.get(
                "ROLEPLAY_DATA_DIR",
                Path(__file__).resolve().parent.parent.parent,
            )
        )

    def _resolve(self, raw: str) -> Path:
        """Resolve a possibly-relative path against the data dir.

        Absolute values pass through unchanged. Relative values are
        joined onto ``self.data_dir`` so a bare ``conversations.db``
        in ``.env`` (or in code) lands inside the active data dir.
        """
        p = Path(raw)
        if p.is_absolute():
            return p
        return self.data_dir / p

    @property
    def effective_db_path(self) -> Path:
        """Absolute SQLite path — relative ``db_path`` resolves under the data dir."""
        return self._resolve(self.db_path)

    @property
    def effective_chroma_persist_dir(self) -> Path:
        """Absolute Chroma directory — relative values resolve under the data dir."""
        return self._resolve(self.chroma_persist_dir)

    @property
    def effective_upload_dir(self) -> Path:
        """Absolute uploads directory — relative values resolve under the data dir.

        The avatar folder sits one level below this path so the public
        URL stays ``/uploads/avatars/…`` regardless of where uploads
        live on disk.
        """
        return self._resolve(self.upload_dir)

    @property
    def db_url_for_alembic(self) -> str:
        """Full async SQLAlchemy URL for the configured SQLite database.

        Used by Alembic's env.py to stay in sync with the app's DB path.
        """
        path = str(self.effective_db_path)
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
        from the same physical location. The avatar folder sits one level
        below ``upload_dir`` so the public URL stays ``/uploads/avatars/…``.
        """
        return self.effective_upload_dir / "avatars"
