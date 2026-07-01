"""File upload routes for assistant/agent threads."""

from dataclasses import dataclass

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from api.deps import ContainerDep
from app.application.dto import ThreadFileDTO

router = APIRouter()


@dataclass
class _FastAPIUploadedFile:
    """Adapter from ``fastapi.UploadFile`` to ``app.application.ports.UploadedFile``.

    The application layer depends on the framework-independent
    ``UploadedFile`` protocol rather than on ``fastapi.UploadFile`` so
    it stays presentation-agnostic (review2.md). ``UploadFile`` has
    its bytes behind a ``.file`` attribute (``SpooledTemporaryFile``),
    so we expose a single ``read(size)`` that delegates to it.
    """

    file: UploadFile

    @property
    def filename(self) -> str | None:
        return self.file.filename

    @property
    def size(self) -> int | None:
        return self.file.size

    def read(self, size: int = -1) -> bytes:
        # ``SpooledTemporaryFile.read`` returns bytes synchronously,
        # matching the protocol. No event-loop blocking — the upload
        # service reads this inside an executor.
        return self.file.file.read(size)


@router.post("/{thread_id}/files")
async def upload_file(
    thread_id: int,
    bot_id: int,
    file: UploadFile = File(...),
    container: ContainerDep = None,
) -> ThreadFileDTO:
    """Upload a file to a thread. Only for assistant/agent bots."""
    if container is None or container.upload is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload service not available",
        )
    return await container.upload.upload(thread_id, bot_id, _FastAPIUploadedFile(file=file))


@router.get("/{thread_id}/files")
async def list_files(
    thread_id: int,
    container: ContainerDep,
) -> list[ThreadFileDTO]:
    """List all uploaded files for a thread."""
    if container.upload is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload service not available",
        )
    return await container.upload.list_files(thread_id)


@router.delete("/{thread_id}/files/{file_id}")
async def delete_file(
    thread_id: int,
    file_id: int,
    container: ContainerDep,
):
    """Delete an uploaded file."""
    if container.upload is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload service not available",
        )
    await container.upload.delete_file(file_id)
    return {"ok": True}


@router.get("/{thread_id}/messages/{message_id}/files")
async def list_message_files(
    thread_id: int,
    message_id: int,
    container: ContainerDep,
) -> list[ThreadFileDTO]:
    """List files attached to a specific message."""
    if container.upload is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload service not available",
        )
    return await container.upload.list_files_for_message(message_id)
