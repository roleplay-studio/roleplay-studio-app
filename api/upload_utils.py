"""Helpers for bounded UploadFile reads and writes."""

from pathlib import Path

from fastapi import HTTPException, UploadFile, status

CHUNK_SIZE = 1024 * 1024


async def read_upload_file_limited(file: UploadFile, max_bytes: int) -> bytes:
    """Read an upload into memory while enforcing a hard byte limit."""
    data = bytearray()
    while True:
        chunk = await file.read(CHUNK_SIZE)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File too large. Maximum size is {max_bytes} bytes",
            )
    return bytes(data)


async def save_upload_file_limited(
    file: UploadFile, destination: str | Path, max_bytes: int
) -> int:
    """Stream an upload to disk while enforcing a hard byte limit."""
    destination = Path(destination)
    total = 0
    try:
        with destination.open("wb") as output:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"File too large. Maximum size is {max_bytes} bytes",
                    )
                output.write(chunk)
    except HTTPException:
        destination.unlink(missing_ok=True)
        raise
    return total
