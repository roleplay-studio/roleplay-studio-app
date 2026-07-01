"""Knowledge base routes."""

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.deps import ContainerDep
from api.schemas import KnowledgeRequest
from api.upload_utils import read_upload_file_limited
from app.application.dto import AddKnowledgeEntryCommand, AddKnowledgeFileCommand, KnowledgeEntryDTO

router = APIRouter()
MAX_KNOWLEDGE_UPLOAD_SIZE = 20 * 1024 * 1024


class TestSearchRequest(BaseModel):
    query: str
    top_k: int = 5


class TestSearchResult(BaseModel):
    content: str
    score: float


@router.get("/{bot_id}", response_model=list[KnowledgeEntryDTO])
async def list_knowledge(bot_id: int, container: ContainerDep):
    return await container.knowledge.list_entries(bot_id)


@router.post("/{bot_id}", response_model=dict, status_code=201)
async def add_knowledge(bot_id: int, body: KnowledgeRequest, container: ContainerDep):
    try:
        command = AddKnowledgeEntryCommand(
            bot_id=bot_id,
            content=body.content,
        )
        await container.knowledge.add_entry(command)
        return {"ok": True}
    except Exception as exc:
        detail = str(exc)
        if "embedding with dimension" in detail and "got" in detail:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Embedding dimension mismatch — you changed the embedding model. "
                f"Please reindex via /api/config/reindex and re-add knowledge entries. "
                f"({detail})",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post("/{bot_id}/upload", response_model=dict, status_code=201)
async def upload_knowledge_file(
    bot_id: int,
    file: UploadFile = File(...),
    container: ContainerDep = None,
):
    """Upload a file (txt, md, docx, pdf) to the knowledge base."""
    try:
        content = await read_upload_file_limited(file, MAX_KNOWLEDGE_UPLOAD_SIZE)
        command = AddKnowledgeFileCommand(
            bot_id=bot_id,
            file_content=content,
            file_name=file.filename or "unknown.txt",
            mime_type=file.content_type or "text/plain",
        )
        result = await container.knowledge.add_file(command)
        return result
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except Exception as exc:
        detail = str(exc)
        if "embedding with dimension" in detail and "got" in detail:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Embedding dimension mismatch — you changed the embedding model. "
                f"Please reindex via /api/config/reindex and re-add knowledge entries. "
                f"({detail})",
            )
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


@router.delete("/{bot_id}/{entry_id}")
async def delete_knowledge(bot_id: int, entry_id: str, container: ContainerDep):
    try:
        await container.knowledge.delete_entry(bot_id, entry_id)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{bot_id}/file/{file_name}")
async def delete_knowledge_file(bot_id: int, file_name: str, container: ContainerDep):
    """Delete all chunks belonging to a specific file."""
    try:
        deleted = await container.knowledge.delete_file_chunks(bot_id, file_name)
        return {"ok": True, "deleted": deleted}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/{bot_id}/{entry_id}")
async def update_knowledge(
    bot_id: int, entry_id: str, body: KnowledgeRequest, container: ContainerDep
):
    """Update a knowledge entry."""
    try:
        await container.knowledge.update_entry(bot_id, entry_id, body.content)
        return {"ok": True}
    except Exception as exc:
        detail = str(exc)
        # Detect embedding dimension mismatch — may need reindex
        if "embedding with dimension" in detail and "got" in detail:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Embedding dimension mismatch — you changed the embedding model. "
                f"Please reindex via /api/config/reindex and re-add knowledge entries. "
                f"({detail})",
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


@router.post("/{bot_id}/test-search")
async def test_search_knowledge(bot_id: int, body: TestSearchRequest, container: ContainerDep):
    """Search knowledge base and return results with similarity scores — for UI testing."""
    try:
        results = await container.knowledge.test_search(bot_id, body.query, body.top_k)
        return {"results": [{"content": c, "score": s} for c, s in results]}
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
