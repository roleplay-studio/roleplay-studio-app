"""Setup wizard routes — first-run configuration."""

import logging
import os
import sys
from pathlib import Path

from dotenv import set_key
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from api.bot_loader import load_from_json, load_from_png
from api.bots_registry import list_starter_bots
from api.constants import PROVIDERS
from api.deps import ContainerDep
from api.schemas import ConfigureRequest
from app.bootstrap import reset_container
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/providers")
async def list_providers():
    """Return available LLM providers."""
    return [{"id": pid, **info} for pid, info in PROVIDERS.items()]


@router.get("/status")
async def setup_status(container: ContainerDep):
    """Check if initial setup is needed."""
    settings = Settings.from_env()
    needs_api_key = settings.llm_api_key is None

    bots = await container.bots.list_bots()
    needs_bot = len(bots) == 0

    return {
        "needs_setup": needs_api_key or needs_bot,
        "needs_api_key": needs_api_key,
        "needs_bot": needs_bot,
        "api_key_configured": not needs_api_key,
        "bot_count": len(bots),
    }


@router.post("/configure")
async def setup_configure(body: ConfigureRequest, container: ContainerDep):
    """Save provider, API key, model, and create a starter bot."""

    # Save env file in the data directory
    data_dir = Path(os.environ.get("ROLEPLAY_DATA_DIR", "."))
    env_path = data_dir / ".env"
    env_path.parent.mkdir(parents=True, exist_ok=True)

    # Determine values
    provider = body.provider
    base_url = body.base_url or PROVIDERS.get(provider, {}).get("default_base_url", "")
    api_key = body.api_key or ""
    model = body.chat_model or ""

    # Apply to env file using dotenv helpers
    set_key(str(env_path), "LLM_PROVIDER", provider)
    if base_url:
        set_key(str(env_path), "LLM_BASE_URL", base_url)
    if api_key:
        set_key(str(env_path), "LLM_API_KEY", api_key)
    if model:
        set_key(str(env_path), "CHAT_MODEL", model)

    # Apply to current process
    env_vars = [
        ("LLM_PROVIDER", provider),
        ("LLM_BASE_URL", base_url),
        ("LLM_API_KEY", api_key),
        ("CHAT_MODEL", model),
    ]
    for k, v in env_vars:
        if v:
            os.environ[k] = v
    # If no key and provider doesn't need one, ensure key is cleared
    if not PROVIDERS.get(provider, {}).get("needs_key", True):
        os.environ.pop("LLM_API_KEY", None)

    # Bot creation happens through POST /import-bots (selected by the user
    # on the last wizard step). /configure only persists provider + env,
    # it does not auto-create a starter bot.

    reset_container()

    return {
        "ok": True,
        "provider": provider,
        "base_url": base_url,
        "chat_model": model,
    }


# ── Starter-bot picker (last wizard step) ──────────────────────────


class ImportStarterBotsRequest(BaseModel):
    """Request body for ``POST /api/setup/import-bots``.

    ``ids`` is the list of starter-bot ids (on-disk stems) the user picked
    in the wizard. Unknown ids are reported back in ``skipped`` and the
    whole import keeps going for the rest.
    """

    ids: list[str] = []


@router.get("/starter-bots")
async def list_starter_bots_endpoint():
    """List starter bots shipped in ``bots_examples/``.

    Returns an empty list if the directory is missing — the wizard UI is
    supposed to render a "no starter bots" state in that case.
    """
    return list_starter_bots()


@router.post("/import-bots")
async def import_starter_bots_endpoint(body: ImportStarterBotsRequest, container: ContainerDep):
    """Bulk-import the selected starter bots.

    Each id maps to a file in ``bots_examples/`` (``.json`` or ``.png``). The
    import uses :class:`BotImportService` so the avatar pipeline (constrain +
    resize) matches the rest of the app. Returns one entry per requested id
    so the UI can surface partial failures.
    """
    if not body.ids:
        return {"imported": [], "skipped": []}

    if container.bot_import is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot import service unavailable",
        )

    registry = {b["id"]: b for b in list_starter_bots()}

    imported: list[dict] = []
    skipped: list[dict] = []
    for bot_id in body.ids:
        entry = registry.get(bot_id)
        if not entry:
            skipped.append({"id": bot_id, "reason": "unknown_id"})
            continue
        if entry.get("error"):
            skipped.append({"id": bot_id, "reason": entry["error"]})
            continue

        # Re-parse from disk — registry payload is the *display* card, the
        # importer needs the full personality string which we don't ship
        # over the wire in /starter-bots to keep the payload small.
        examples_dir = _examples_dir()
        path = examples_dir / f"{bot_id}.{entry['format']}"
        if not path.exists():
            skipped.append({"id": bot_id, "reason": f"file missing: {path.name}"})
            continue
        try:
            card = load_from_png(path) if entry["format"] == "png" else load_from_json(path)
            avatar_bytes = path.read_bytes() if entry["format"] == "png" else None
        except (OSError, ValueError) as e:
            skipped.append({"id": bot_id, "reason": str(e)})
            continue

        try:
            new_bot_id = await container.bot_import.import_from_starter(
                card, avatar_bytes=avatar_bytes
            )
        except Exception as e:
            logger.exception("Failed to import starter bot %s", bot_id)
            skipped.append({"id": bot_id, "reason": str(e)})
            continue

        imported.append({"id": bot_id, "bot_id": new_bot_id, "name": card["name"]})

    return {"imported": imported, "skipped": skipped}


def _examples_dir() -> Path:
    """Resolve the bots_examples dir for the current runtime.

    Mirrors :func:`api.bots_registry._examples_dir` — kept as a tiny local
    copy so the route can find the on-disk file the registry already
    validated, without re-running the registry in a different process.
    """
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path.cwd()))
    else:
        base = Path(__file__).resolve().parent.parent.parent
    return base / "bots_examples"
