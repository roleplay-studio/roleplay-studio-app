"""Entrypoint for PyInstaller — runs hypercorn with the FastAPI app."""

import asyncio
import os
import sys

# Ensure we can find the api/ and app/ modules
if getattr(sys, "frozen", False):
    # Inside PyInstaller: modules unpacked to _MEIPASS
    _BASE_DIR = sys._MEIPASS
else:
    # Dev mode: project root is one level up from backend/
    _BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if _BASE_DIR not in sys.path:
    sys.path.insert(0, _BASE_DIR)

# ── Detect data dir ──────────────────────────────────────────────
# Use ~/Library/Application Support (Tauri .app bundle or standalone PyInstaller)
# In dev mode fall back to project root
_APP_SUPPORT = os.path.expanduser("~/Library/Application Support/com.nyashkin.roleplay-studio")
if getattr(sys, "frozen", False):
    # PyInstaller: always use stable Application Support dir, create if needed
    _DATA_DIR = _APP_SUPPORT
    os.makedirs(_DATA_DIR, exist_ok=True)
else:
    # Dev mode: always use project root
    _DATA_DIR = _BASE_DIR

os.environ.setdefault("ROLEPLAY_DATA_DIR", _DATA_DIR)

# ── Ensure data directories exist ────────────────────────────────
os.makedirs(os.path.join(_DATA_DIR, "uploads"), exist_ok=True)

# ── Load .env from data dir ──────────────────────────────────────
from dotenv import load_dotenv  # noqa: E402

env_path = os.path.join(_DATA_DIR, ".env")
if os.path.exists(env_path):
    load_dotenv(env_path)
    print(f"[backend] Loaded .env from {env_path}")
else:
    print(f"[backend] No .env found at {env_path} — setup required")

# ── Start server ─────────────────────────────────────────────────

from hypercorn.asyncio import serve  # noqa: E402
from hypercorn.config import Config  # noqa: E402

from api.main import app  # noqa: E402

# Surface our own INFO logs (chat summarization, payload dumps, etc.)
# alongside hypercorn's. Without this the root logger stays at WARNING
# and any logger.info(...) in app/ is silently dropped.
# m20: delegate to the structlog-aware configure_logging() helper
# in app.infrastructure.logging. Operators can flip LOG_FORMAT=json
# for ELK/Datadog ingestion without changing any logger.info(...)
# call sites.
from app.infrastructure.config import Settings  # noqa: E402
from app.infrastructure.logging import configure_logging  # noqa: E402

configure_logging(Settings.from_env())


async def main():
    config = Config()
    # Bind address: defaults to 127.0.0.1:55245 (the production
    # Tauri launcher behaviour), but the Docker dev stack needs
    # 0.0.0.0 so the frontend container can reach the backend by
    # service name. HYPERCORN_BIND overrides both host and port.
    bind_addr = os.environ.get("HYPERCORN_BIND", "127.0.0.1:55245")
    config.bind = [bind_addr]
    config.use_reloader = False
    # Honour $LOG_LEVEL (set by the docker-compose env block) so
    # operators can flip to WARNING without rebuilding. Defaults
    # to INFO to match the pre-Docker behaviour.
    config.loglevel = os.environ.get("LOG_LEVEL", "info").lower()
    # Allow larger uploads (10 MB default, bump to 100 MB)
    try:
        config.limits.max_body = 100 * 1024 * 1024  # 100 MB
    except AttributeError:
        pass  # older Hypercorn doesn't have limits
    print(f"[backend] Starting Roleplay Studio API on {bind_addr}")
    print(f"[backend] Data directory: {_DATA_DIR}")
    await serve(app, config)


if __name__ == "__main__":
    asyncio.run(main())
