"""Upload service — handles file uploads, text extraction, and vision description.

This service is presentation-framework agnostic: it depends on the
``UploadedFile`` protocol from ``app.application.ports`` rather than
``fastapi.UploadFile``, and raises application-layer exceptions
(``NotFoundError`` / ``UploadError``) instead of HTTPException. The
route adapter maps those to HTTP responses via a global
``ApplicationError`` exception handler registered in
``api/main.py``. That keeps the application layer free of any
``fastapi`` import (review2.md: app/application must not import
fastapi).
"""

import asyncio
import base64
import logging
import os
import uuid

from app.application.dto import ThreadFileDTO
from app.application.exceptions import NotFoundError, UploadError
from app.application.ports import (
    BotRepository,
    LLMPort,
    ThreadFileRepository,
    UploadedFile,
)
from app.domain.enums import BotType
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
_CHUNK_SIZE = 1024 * 1024  # 1 MiB read chunks for the bounded stream


class _UploadTooLargeError(Exception):
    """Internal signal — translated to UploadError in upload()."""


class UploadService:
    def __init__(
        self,
        files_repo: ThreadFileRepository,
        bots: BotRepository,
        llm: LLMPort | None = None,
        settings: Settings | None = None,
    ):
        self._files = files_repo
        self._bots = bots
        self._llm = llm
        self._settings = settings or Settings.from_env()

    @property
    def upload_dir(self) -> str:
        # ``effective_upload_dir`` is absolute; relative ``upload_dir``
        # from .env is resolved against the data dir at access time.
        return str(self._settings.effective_upload_dir)

    async def upload(self, thread_id: int, bot_id: int, file: UploadedFile) -> ThreadFileDTO:
        """Validate, save file to disk, extract text, and persist metadata."""
        # 1. Check bot type
        bot = await self._bots.get(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot {bot_id} not found")
        if bot.bot_type not in (BotType.ASSISTANT, BotType.AGENT):
            raise UploadError(
                "File upload is only available for assistant and agent bots",
                code="upload_bot_type_unsupported",
            )

        # 2. Validate filename and extension. We keep the user-supplied
        #    ``filename`` as a *display* name only and never reuse it in
        #    the on-disk path — that closes the path-traversal vector
        #    called out in review2.md.
        if file.filename is None:
            raise UploadError("File must have a name", code="upload_missing_filename")

        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise UploadError(
                f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
                code="upload_unsupported_type",
            )

        # 3. Honour the size cap declared by the client, but do NOT
        #    trust it as a hard limit — we re-enforce it while reading
        #    the stream (Fix 8 in the review). ``file.size`` is advisory.
        if file.size is not None and file.size > MAX_FILE_SIZE:
            raise UploadError(
                f"File too large: {file.size} bytes (max {MAX_FILE_SIZE})",
                http_status=413,
                code="upload_too_large",
            )

        # 4. Determine file_type
        image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        if ext in image_exts:
            file_type = "image"
        elif ext == ".pdf":
            file_type = "pdf"
        else:
            file_type = "text"

        # 5. Save to disk. The on-disk name is a fresh uuid — we never
        #    trust the user-supplied filename as a path component.
        storage_dir = os.path.join(self.upload_dir, str(thread_id))
        os.makedirs(storage_dir, exist_ok=True)
        storage_path = os.path.join(storage_dir, f"{uuid.uuid4().hex}{ext}")

        # Defence in depth: even with a uuid name, verify the resolved
        # path stays inside storage_dir. Catches any future code change
        # that accidentally starts trusting user input here again.
        storage_dir_resolved = os.path.realpath(storage_dir)
        storage_path_resolved = os.path.realpath(storage_path)
        if (
            not storage_path_resolved.startswith(storage_dir_resolved + os.sep)
            and storage_path_resolved != storage_dir_resolved
        ):
            raise UploadError("Invalid filename", code="upload_invalid_filename")

        try:
            await self._write_bounded(file, storage_path)
        except _UploadTooLargeError as exc:
            raise UploadError(
                f"File too large (max {MAX_FILE_SIZE} bytes)",
                http_status=413,
                code="upload_too_large",
            ) from exc
        except Exception as exc:
            # Roll back partial upload so a half-written file doesn't
            # sit in the upload dir as dead weight (Fix 8 secondary).
            try:
                os.remove(storage_path)
            except OSError:
                pass
            raise UploadError(
                "Failed to save file",
                code="upload_save_failed",
            ) from exc

        # 6. Extract text
        extracted_text: str | None = None
        try:
            if file_type == "text":
                extracted_text = self._extract_text(storage_path)
            elif ext == ".pdf":
                extracted_text = self._extract_pdf(storage_path)
            elif file_type == "image":
                extracted_text = await self._describe_image(storage_path)
        except Exception as exc:
            logger.warning("Text extraction failed for %s: %s", file.filename, exc)
            # Don't fail the upload — just leave extracted_text as None

        # 7. Save to DB
        return await self._files.save(
            thread_id=thread_id,
            filename=file.filename,
            file_type=file_type,
            storage_path=storage_path,
            extracted_text=extracted_text,
        )

    async def _write_bounded(self, file: UploadedFile, storage_path: str) -> None:
        """Read ``file`` in 1 MiB chunks and write to ``storage_path``.

        Enforces ``MAX_FILE_SIZE`` while reading (so we never trust the
        client-declared ``file.size``), and runs the blocking
        ``open()``/``write()`` loop in the default executor so the
        event loop stays responsive. On overflow, the partial file is
        removed before raising.
        """
        loop = asyncio.get_running_loop()

        def _blocking_write() -> None:
            total = 0
            with open(storage_path, "wb") as out:
                while True:
                    chunk = file.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_FILE_SIZE:
                        out.close()
                        try:
                            os.remove(storage_path)
                        except OSError:
                            pass
                        raise _UploadTooLargeError
                    out.write(chunk)

        await loop.run_in_executor(None, _blocking_write)

    def _extract_text(self, path: str) -> str:
        """Read plain text file."""
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    def _extract_pdf(self, path: str) -> str:
        """Extract text from PDF using PyMuPDF."""
        try:
            import fitz  # PyMuPDF
        except ImportError as exc:
            raise UploadError(
                "PyMuPDF (fitz) is not installed. Install it with: pip install PyMuPDF",
                code="upload_pdf_unavailable",
            ) from exc

        doc = fitz.open(path)
        pages = []
        max_pages = min(len(doc), 30)  # Limit to first 30 pages
        for i in range(max_pages):
            page_text = doc[i].get_text()
            if page_text.strip():
                pages.append(page_text)
        doc.close()
        return "\n\n".join(pages)

    async def _describe_image(self, path: str) -> str:
        """Describe an image using a vision-capable LLM."""
        if self._llm is None:
            return "[Image upload — no vision LLM available]"

        # M-review2: read the file in the default executor so the
        # event loop isn't blocked on the file read for large images.
        # base64 encoding is CPU-bound and also moved off the loop.
        loop = asyncio.get_running_loop()

        def _read_and_encode() -> str:
            with open(path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")

        image_data = await loop.run_in_executor(None, _read_and_encode)

        ext = os.path.splitext(path)[1].lower().lstrip(".")
        mime = f"image/{ext}"
        if ext == "jpg":
            mime = "image/jpeg"

        # Build multimodal message
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this image in detail. What do you see? "
                            "Include relevant visual details, text (if any), "
                            "objects, people, setting, mood, and colors. "
                            "Be thorough but concise — aim for 2-4 sentences."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{image_data}"},
                    },
                ],
            }
        ]

        try:
            description = await self._llm.generate_response(messages)
            return description if description else "[Image uploaded — no description available]"
        except Exception as exc:
            logger.exception("Vision description failed for %s", os.path.basename(path))
            return f"[Image uploaded — vision description failed: {exc}]"

    async def list_files(self, thread_id: int) -> list[ThreadFileDTO]:
        return await self._files.list_for_thread(thread_id)

    async def delete_file(self, file_id: int) -> None:
        await self._files.delete(file_id)

    async def list_files_for_message(self, message_id: int) -> list[ThreadFileDTO]:
        return await self._files.list_for_message(message_id)
