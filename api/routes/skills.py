"""Skills REST routes. See spec §6.6.

Layered on top of ``SkillService`` (no business logic here). The
service layer maps ``SkillRepository`` outcomes to the application
exception hierarchy (ValidationError, NotFoundError, ConflictError),
and the existing ``application_error_handler`` in ``api/main.py``
turns those into HTTP responses (see spec §6.4 for the 409 path).
"""
from fastapi import APIRouter, HTTPException, status

from api.deps import ContainerDep
from app.application.dto import CreateSkillCommand, SkillDTO, UpdateSkillCommand

router = APIRouter()


# ── Library: /api/skills ─────────────────────────────────────────


@router.get("", response_model=list[SkillDTO])
async def list_skills(
    q: str | None = None,
    tag: str | None = None,
    container: ContainerDep = None,
) -> list[SkillDTO]:
    """List all skills in the global library.

    Optional filters:
    - ``q`` — case-insensitive substring match on name + description
    - ``tag`` — case-insensitive exact match against any tag
    """
    if container.skills is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skills service unavailable",
        )
    return await container.skills.list_skills(q=q, tag=tag)


@router.get("/{skill_id}", response_model=SkillDTO)
async def get_skill(skill_id: int, container: ContainerDep) -> SkillDTO:
    """Fetch one skill by id (full DTO including ``instruction``)."""
    if container.skills is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skills service unavailable",
        )
    return await container.skills.get_skill(skill_id)


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_skill(body: CreateSkillCommand, container: ContainerDep) -> dict:
    """Create a new skill. 409 on duplicate name (via application_error_handler)."""
    if container.skills is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skills service unavailable",
        )
    skill_id = await container.skills.create_skill(body)
    return {"id": skill_id}


@router.put("/{skill_id}")
async def update_skill(
    skill_id: int,
    body: UpdateSkillCommand,
    container: ContainerDep,
) -> dict:
    """Partial update — only the supplied fields are touched."""
    if container.skills is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skills service unavailable",
        )
    await container.skills.update_skill(skill_id, body)
    return {"ok": True}


@router.delete("/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_skill(skill_id: int, container: ContainerDep) -> None:
    """Delete a skill. 409 Conflict with ``attached_to`` if bots use it."""
    if container.skills is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Skills service unavailable",
        )
    await container.skills.delete_skill(skill_id)
    return None
