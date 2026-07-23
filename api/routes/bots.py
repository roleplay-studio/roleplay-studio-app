"""Bot CRUD routes."""

import json
import os
import uuid
from pathlib import Path
from urllib.parse import quote

from character_card import (
    CharacterCardParseError,
    build_character_card_json,
    embed_card_in_png,
)
from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from api.constants import ALLOWED_EXTENSIONS, UPLOADS_DIR
from api.deps import ContainerDep
from api.schemas import (
    CategoryAddRequest,
    CategoryRenameRequest,
    CategoryReplaceRequest,
    ImportBotRequest,
    UpdateBotRequest,
)
from api.upload_utils import read_upload_file_limited, save_upload_file_limited
from app.application.dto import (
    AddKnowledgeEntryCommand,
    BotResponse,
    BotSkillDTO,
    BotVersionDTO,
    CreateBotCommand,
    SkillDTO,
    ThreadDTO,
    UpdateBotCommand,
    UpdateBotSkillsCommand,
)
from app.application.exceptions import NotFoundError
from app.application.services.bot_version import to_dto
from app.infrastructure.character_card_extras import generate_placeholder_png
from app.infrastructure.image_utils import constrain_image, resize_avatar

router = APIRouter()

os.makedirs(UPLOADS_DIR, exist_ok=True)
MAX_AVATAR_SIZE = 10 * 1024 * 1024
MAX_CHAT_IMPORT_SIZE = 20 * 1024 * 1024
MAX_IMPORT_SIZE = 20 * 1024 * 1024
_IMPORT_EXTS = {".json", ".png", ".webp", ".jpg", ".jpeg"}
# TODO(for-assistant): вынести переменные в общие настройки

# ── Categories ───────────────────────────────────────────────────────


def _require_settings(container):
    """The SettingsService must always be wired up, but the route
    layer treats a misconfigured container as a 503 — the rest of the
    app would already be unusable without it (see api/main.py)."""
    svc = getattr(container, "settings", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings service unavailable",
        )
    return svc


@router.get("/categories", response_model=list[str])
async def list_categories(container: ContainerDep):
    """Return the user-managed bot category list (seeded on first read)."""
    svc = _require_settings(container)
    return await svc.list_bot_categories()


@router.post("/categories", response_model=list[str], status_code=status.HTTP_201_CREATED)
async def add_category(body: CategoryAddRequest, container: ContainerDep):
    """Append a new category, deduping against existing entries."""
    svc = _require_settings(container)
    return await svc.add_category(body.name)


@router.post("/categories/rename", response_model=list[str])
async def rename_category(body: CategoryRenameRequest, container: ContainerDep):
    """Rename a category in place. Order-preserving."""
    svc = _require_settings(container)
    return await svc.rename_category(body.old_name, body.new_name)


@router.delete("/categories/{name}", response_model=list[str])
async def delete_category(name: str, container: ContainerDep):
    """Remove a category. Bots that referenced it keep the legacy
    string (the picker hides it; ``categories_invalid`` surfaces it)."""
    svc = _require_settings(container)
    return await svc.delete_category(name)


@router.put("/categories", response_model=list[str])
async def replace_categories(body: CategoryReplaceRequest, container: ContainerDep):
    """Atomically replace the whole category list."""
    svc = _require_settings(container)
    return await svc.replace_all(body.categories)


# ── Upload (must be before /{bot_id} to avoid route conflicts) ──────


@router.post("/upload/avatar")
async def upload_avatar(file: UploadFile = File(...)):
    """Upload an avatar image, returns paths for original and resized versions."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Extension '{ext}' not allowed. Use: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    stem = uuid.uuid4().hex
    unique_name = f"{stem}{ext}"
    file_path = os.path.join(UPLOADS_DIR, unique_name)

    os.makedirs(UPLOADS_DIR, exist_ok=True)
    await save_upload_file_limited(file, file_path, MAX_AVATAR_SIZE)

    # Constrain original to 1024px max, then generate thumbnails
    constrain_image(file_path, file_path, max_dim=1024)
    resized = resize_avatar(file_path, UPLOADS_DIR, stem, ext)

    return {
        "path": f"/uploads/avatars/{unique_name}",
        "path_500": f"/uploads/avatars/{stem}_500{ext}" if 500 in resized else None,
        "path_200": f"/uploads/avatars/{stem}_200{ext}" if 200 in resized else None,
        "path_50": f"/uploads/avatars/{stem}_50{ext}" if 50 in resized else None,
    }


# ── Bot CRUD ─────────────────────────────────────────────────────────


@router.get("", response_model=list[BotResponse])
async def list_bots(container: ContainerDep):
    """List all bots with thread counts.

    Each bot response carries ``categories_invalid`` (categories
    that were removed from the user-managed list) so the UI can
    highlight "stale" chips instead of silently hiding them.
    """
    bots_with_counts = await container.bots.list_bots_with_counts()
    settings_svc = getattr(container, "settings", None)
    valid_categories = (
        set(await settings_svc.list_bot_categories())
        if settings_svc is not None
        else None
    )
    # Resolve live skill IDs so BotResponse.skills_invalid is populated
    # for orphan refs (a skill that was deleted but bot.skill_ids still
    # points at). Graceful degradation: when the skill service is
    # missing, valid_skill_ids is None and skills_invalid stays empty.
    # See skill-api OCR review finding 2026-07-17 (CRITICAL).
    valid_skill_ids: set[int] | None = None
    if getattr(container, "skills", None) is not None:
        valid_skill_ids = await container.skills.list_all_skill_ids()
    return [
        BotResponse.from_orm_bot(
            bot,
            count,
            valid_categories=valid_categories,
            valid_skill_ids=valid_skill_ids,
        )
        for bot, count in bots_with_counts
    ]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_bot(command: CreateBotCommand, container: ContainerDep):
    # Filter the user-supplied category list against the current
    # managed catalog so ``Bot.categories`` never holds a name that's
    # been removed. Returns silently — picker hides unknowns anyway,
    # but persisting them makes the "stale" list grow unboundedly.
    settings_svc = getattr(container, "settings", None)
    if settings_svc is not None:
        command.categories = await settings_svc.filter_valid(command.categories)
    bot_id = await container.bots.create_bot(command)
    return {"id": bot_id}


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(bot_id: int, container: ContainerDep):
    try:
        bot, thread_count = await container.bots.get_bot_with_count(bot_id)
        settings_svc = getattr(container, "settings", None)
        valid = (
            set(await settings_svc.list_bot_categories())
            if settings_svc is not None
            else None
        )
        # Skill cross-reference for skills_invalid (OCR review 2026-07-17).
        valid_skill_ids: set[int] | None = None
        if getattr(container, "skills", None) is not None:
            valid_skill_ids = await container.skills.list_all_skill_ids()
        return BotResponse.from_orm_bot(
            bot,
            thread_count,
            valid_categories=valid,
            valid_skill_ids=valid_skill_ids,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{bot_id}")
async def update_bot(bot_id: int, body: UpdateBotRequest, container: ContainerDep):
    try:
        # Same orphan-stripping on update — never persist a category
        # that's been deleted since the bot was created or last edited.
        settings_svc = getattr(container, "settings", None)
        if settings_svc is not None:
            body.categories = await settings_svc.filter_valid(body.categories)
        command = UpdateBotCommand(
            bot_id=bot_id,
            name=body.name,
            personality=body.personality,
            first_message=body.first_message,
            scenario=body.scenario,
            description=body.description,
            avatar_path=body.avatar_path,
            categories=body.categories,
            bot_type=body.bot_type,
            alternate_greetings=body.alternate_greetings,
            mes_example=body.mes_example or "",
            dynamic_system_prompt=body.dynamic_system_prompt,
            world_state_prompt=body.world_state_prompt,
        )
        await container.bots.update_bot(command)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{bot_id}")
async def delete_bot(bot_id: int, container: ContainerDep):
    try:
        await container.bots.delete_bot(bot_id)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


# ── Bot Versions ─────────────────────────────────────────────────────


class CreateBotVersionRequest(BaseModel):
    note: str = ""
    # TODO(for-assistant): такие классы нужнор выносить в отдельный файл


@router.get("/{bot_id}/versions", response_model=list[BotVersionDTO])
async def list_bot_versions(bot_id: int, container: ContainerDep):
    """List versions of a bot, newest first (no snapshot payload)."""
    if container.bot_versions is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot versioning unavailable",
        )
    try:
        versions = await container.bot_versions.list_versions(bot_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return [to_dto(v, include_snapshot=False) for v in versions]


@router.post(
    "/{bot_id}/versions",
    response_model=BotVersionDTO,
    status_code=status.HTTP_201_CREATED,
)
async def create_bot_version(
    bot_id: int,
    body: CreateBotVersionRequest,
    container: ContainerDep,
):
    """Manually snapshot the current bot state with an optional note."""
    if container.bot_versions is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot versioning unavailable",
        )
    try:
        version = await container.bot_versions.create_version(
            bot_id=bot_id, note=body.note or "", source="manual"
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return to_dto(version, include_snapshot=True)


@router.get("/{bot_id}/versions/{version_id}", response_model=BotVersionDTO)
async def get_bot_version(
    bot_id: int,
    version_id: int,
    container: ContainerDep,
):
    """Get a single version with its full snapshot payload."""
    if container.bot_versions is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot versioning unavailable",
        )
    try:
        version = await container.bot_versions.get_version(version_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if version.bot_id != bot_id:
        # Hidden behind the same id space — never let a wrong bot_id
        # silently expose another bot's snapshot.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} does not belong to bot {bot_id}",
        )
    return to_dto(version, include_snapshot=True)


@router.post("/{bot_id}/versions/{version_id}/restore")
async def restore_bot_version(
    bot_id: int,
    version_id: int,
    container: ContainerDep,
):
    """Restore the bot to the state captured in the version.

    The current state is auto-saved as a new version (with a
    pre-filled note) before the snapshot is applied.
    """
    if container.bot_versions is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot versioning unavailable",
        )
    try:
        version = await container.bot_versions.get_version(version_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if version.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} does not belong to bot {bot_id}",
        )
    await container.bot_versions.restore_version(version_id)
    return {"ok": True, "restored_from": version.version_number}


@router.delete("/{bot_id}/versions/{version_id}")
async def delete_bot_version(
    bot_id: int,
    version_id: int,
    container: ContainerDep,
):
    if container.bot_versions is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot versioning unavailable",
        )
    try:
        version = await container.bot_versions.get_version(version_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if version.bot_id != bot_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} does not belong to bot {bot_id}",
        )
    await container.bot_versions.delete_version(version_id)
    return {"ok": True}


# ── Bot Export / Import ──────────────────────────────────────────────────


def _get_avatar_png(bot, avatar_dir: Path) -> bytes:
    """Return PNG bytes for the bot's avatar, or a generated placeholder."""
    if bot.avatar_path:
        path = avatar_dir / Path(bot.avatar_path).name
        if path.exists():
            data = path.read_bytes()
            if data:
                return data
    return generate_placeholder_png(bot.name or "?")


@router.get("/{bot_id}/export")
async def export_bot(
    bot_id: int,
    format: str = "json",
    container: ContainerDep = None,
):
    """Export a bot as V2 JSON (default) or PNG with an embedded character card."""
    if format not in ("json", "png"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="format must be 'json' or 'png'"
        )

    try:
        bot, _ = await container.bots.get_bot_with_count(bot_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    knowledge_contents = await container.knowledge.get_knowledge_contents(bot_id)
    card_json = build_character_card_json(bot, knowledge_contents=knowledge_contents)

    safe_name = quote(bot.name or "bot", safe="")
    if format == "json":
        return JSONResponse(
            content=card_json,
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.json",
            },
        )

    # PNG: build base image (avatar or placeholder) + embed card.
    # UPLOADS_DIR is already the avatars directory (see api/constants.py),
    # so we pass it directly — do NOT append another "avatars" segment.
    base_png = _get_avatar_png(bot, Path(UPLOADS_DIR))
    out_bytes = embed_card_in_png(base_png, card_json)
    return Response(
        content=out_bytes,
        media_type="image/png",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}.png",
        },
    )


async def _import_from_json(content: bytes, container: ContainerDep) -> dict:
    """Existing JSON import path — preserved verbatim inside the new multipart flow."""
    try:
        body = ImportBotRequest.model_validate_json(content)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid JSON: {exc}",
        )
    # Same orphan-stripping as create/update — an imported character
    # card may carry categories the local user has since deleted.
    settings_svc = getattr(container, "settings", None)
    cats = body.categories
    if settings_svc is not None:
        cats = await settings_svc.filter_valid(cats)
    command = CreateBotCommand(
        name=body.name.strip(),
        personality=body.personality.strip(),
        first_message=body.first_message.strip(),
        scenario=body.scenario,
        description=body.description,
        avatar_path=body.avatar,
        categories=cats,
        bot_type=body.bot_type,
        alternate_greetings=getattr(body, "alternate_greetings", []) or [],
        mes_example=getattr(body, "mes_example", "") or "",
        dynamic_system_prompt=getattr(body, "dynamic_system_prompt", "") or "",
        world_state_prompt=getattr(body, "world_state_prompt", "") or "",
    )
    bot_id = await container.bots.create_bot(command)

    if body.knowledge:
        for entry in body.knowledge:
            entry = entry.strip()
            if entry:
                await container.knowledge.add_entry(
                    AddKnowledgeEntryCommand(bot_id=bot_id, content=entry)
                )

    return {"id": bot_id}


@router.post("/import", response_model=dict, status_code=status.HTTP_201_CREATED)
async def import_bot(
    file: UploadFile = File(...),
    container: ContainerDep = None,
):
    """Import a bot from a JSON or PNG/WebP/JPG character card file (multipart upload)."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in _IMPORT_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}",
        )

    content = await read_upload_file_limited(file, MAX_IMPORT_SIZE)

    if ext == ".json":
        return await _import_from_json(content, container)

    if container.bot_import is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Bot import service unavailable",
        )

    try:
        bot_id = await container.bot_import.import_from_card(content, ext)
    except CharacterCardParseError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return {"id": bot_id}


# ── Thread CRUD ────────────────────────────────────────────────────────


class CreateThreadRequest(BaseModel):
    persona_id: int | None = None


@router.get("/{bot_id}/threads/find")
async def find_thread_by_persona(
    bot_id: int,
    persona_id: int = Query(...),
    container: ContainerDep = None,
):
    thread = await container.threads.find_by_bot_and_persona(bot_id, persona_id)
    if thread is None:
        return {"thread": None}
    return {
        "thread": {
            "id": thread.id,
            "bot_id": thread.bot_id,
            "name": thread.name,
            "persona_id": thread.persona_id,
            "created_at": thread.created_at,
        }
    }


@router.get("/{bot_id}/threads", response_model=list[ThreadDTO])
async def list_bot_threads(bot_id: int, container: ContainerDep):
    return await container.threads.list_threads(bot_id)


@router.post("/{bot_id}/threads", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_thread(
    bot_id: int,
    body: CreateThreadRequest | None = None,
    container: ContainerDep = None,
):
    persona_id = body.persona_id if body else None
    thread_id = await container.threads.create_thread(bot_id, persona_id=persona_id)
    # Save first_message immediately so it appears in the thread on load.
    # We also substitute ``{{user}}`` inline so the persisted row
    # doesn't leak the literal placeholder into the rebuilt history
    # on every subsequent turn (see ChatService.stream_save_first_message
    # for the substitution semantics). Without this, the orchestrator
    # path that goes through ``stream_message`` is fine on the first
    # turn (it substitutes in-flight) but the DB row keeps the raw
    # ``{{user}}`` token, so any future regenerate / retry / re-read
    # from history leaks it.
    try:
        if container.chat is not None:
            bot = await container.bots.get_bot(bot_id)
            if bot and bot.first_message:
                # Resolve the persona up front so the first_message
                # row is persisted with ``{{user}}`` already substituted.
                # A bad / missing persona id is silently treated as
                # "no persona" — the orchestrator will substitute on
                # the first turn instead.
                persona_name: str | None = None
                if persona_id is not None and container.personas is not None:
                    try:
                        persona = await container.personas.get(persona_id)
                    except Exception:
                        # NotFoundError from PersonaService.get (the
                        # persona was deleted between picker and save),
                        # or any other repo failure. Fall through to
                        # "no persona" rather than failing the whole
                        # thread creation.
                        persona = None
                    if persona is not None:
                        persona_name = persona.name
                await container.chat.stream_save_first_message(
                    thread_id, bot_id, persona_name=persona_name
                )
    except Exception:
        pass
    return {"id": thread_id}


@router.post("/{bot_id}/import-chat")
async def import_chat(
    bot_id: int,
    container: ContainerDep,
    file: UploadFile = File(...),
    persona_id: int | None = None,
):
    """Import chat history from a JSON file for this bot."""
    try:
        content = await read_upload_file_limited(file, MAX_CHAT_IMPORT_SIZE)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to read uploaded file",
        )

    try:
        result = await container.threads.import_chat(bot_id, content, persona_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {"ok": True, "thread_id": result.thread_id, "message_count": result.message_count}


# ── Per-bot skills: /api/bots/{bot_id}/skills ──────────────────


@router.get("/{bot_id}/skills", response_model=list[SkillDTO])
async def list_bot_skills(bot_id: int, container: ContainerDep):
    """List the resolved skills attached to a bot.

    Returns the full ``SkillDTO`` (with ``instruction``) for each
    attached skill, in id-ASC order. Orphan IDs (where the underlying
    ``GlobalSkill`` was deleted) are silently skipped (see spec §6.2).
    """
    if container.skills is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skills service unavailable",
        )
    # Verify bot exists first — the service-level resolve returns
    # empty for unknown bots which would otherwise silently 200 with [].
    bot = await container.bots.get_bot(bot_id)
    if bot is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Bot {bot_id} not found"
        )
    skill_ids = json.loads(getattr(bot, "skill_ids", "[]") or "[]")
    return await container.skills.list_for_bot_with_ids(skill_ids)


@router.put("/{bot_id}/skills")
async def update_bot_skills(
    bot_id: int,
    body: UpdateBotSkillsCommand,
    container: ContainerDep,
) -> dict:
    """Replace the bot's skill list with the supplied IDs.

    Returns the resolved ``BotSkillDTO`` list (without ``instruction``)
    so the frontend can update the chips without a second round-trip.
    Validation (limit, existence) lives in the service layer.
    """
    if container.skills is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skills service unavailable",
        )
    skills = await container.skills.update_bot_skills(bot_id, body.skill_ids)
    return {
        "ok": True,
        "skills": [
            BotSkillDTO(id=s.id, name=s.name, description=s.description)
            for s in skills
        ],
    }
