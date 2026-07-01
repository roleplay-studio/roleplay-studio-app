"""Personal user personas CRUD routes."""

import os
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from api.constants import ALLOWED_EXTENSIONS, UPLOADS_DIR
from api.deps import ContainerDep
from api.upload_utils import save_upload_file_limited
from app.application.dto import CreatePersonaCommand, UpdatePersonaCommand, UserPersonaDTO
from app.application.exceptions import NotFoundError
from app.infrastructure.image_utils import constrain_image, resize_avatar

router = APIRouter()
MAX_AVATAR_SIZE = 10 * 1024 * 1024


@router.get("", response_model=list[UserPersonaDTO])
async def list_personas(container: ContainerDep):
    return await container.personas.list()


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_persona(command: CreatePersonaCommand, container: ContainerDep):
    persona_id = await container.personas.create(
        command.name, command.description, command.avatar_path
    )
    return {"id": persona_id}


@router.get("/{persona_id}", response_model=UserPersonaDTO)
async def get_persona(persona_id: int, container: ContainerDep):
    try:
        return await container.personas.get(persona_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{persona_id}")
async def update_persona(persona_id: int, command: UpdatePersonaCommand, container: ContainerDep):
    try:
        command.persona_id = persona_id
        await container.personas.update(
            persona_id, command.name, command.description, command.avatar_path
        )
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{persona_id}")
async def delete_persona(persona_id: int, container: ContainerDep):
    try:
        await container.personas.delete(persona_id)
        return {"ok": True}
    except NotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/upload/avatar")
async def upload_avatar(file: UploadFile = File(...)):
    """Upload an avatar image, returns paths for original and resized versions."""
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Extension '{ext}' not allowed"
        )

    stem = uuid.uuid4().hex
    unique_name = f"{stem}{ext}"
    file_path = os.path.join(UPLOADS_DIR, unique_name)

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
