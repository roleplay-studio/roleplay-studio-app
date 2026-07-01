"""Parse uploaded files (txt, md, docx, pdf) into plain text."""

from __future__ import annotations

from typing import ClassVar


class FileParser:
    """Extract text content from uploaded files."""

    # Supported extensions and their (internal) types
    _EXT_MAP: ClassVar[dict[str, str]] = {
        ".txt": "text",
        ".md": "text",
        ".docx": "docx",
        ".pdf": "pdf",
    }

    # MIME types that map to "just read as text"
    _TEXT_MIMES: ClassVar[set[str]] = {
        "text/plain",
        "text/markdown",
        "text/x-markdown",
        "text/richtext",
    }

    @classmethod
    def parse(cls, content: bytes, file_name: str, mime_type: str) -> str:
        """Parse file content bytes into plain text.

        Args:
            content: Raw file bytes.
            file_name: Original file name (used for extension detection).
            mime_type: MIME type from the upload.

        Returns:
            Extracted plain text.

        Raises:
            ValueError: If the file format is not supported.
        """
        import os

        ext = os.path.splitext(file_name)[1].lower()

        # 1. Try by extension first
        file_type = cls._EXT_MAP.get(ext)

        # 2. Fallback: detect text files by MIME
        if file_type is None:
            if mime_type in cls._TEXT_MIMES or mime_type.startswith("text/"):
                file_type = "text"
            else:
                raise ValueError(
                    f"Unsupported file format: {ext or mime_type}. "
                    f"Supported: {', '.join(sorted(cls._EXT_MAP.keys()))}"
                )

        if file_type == "text":
            return cls._parse_text(content)
        elif file_type == "docx":
            return cls._parse_docx(content)
        elif file_type == "pdf":
            return cls._parse_pdf(content)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

    @staticmethod
    def _parse_text(content: bytes) -> str:
        """Parse plain text / markdown content."""
        if not content:
            return ""
        return content.decode("utf-8", errors="replace")

    @staticmethod
    def _parse_docx(content: bytes) -> str:
        """Parse DOCX file using python-docx."""
        import io

        from docx import Document

        doc = Document(io.BytesIO(content))
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    @staticmethod
    def _parse_pdf(content: bytes) -> str:
        """Parse PDF file using pypdf."""
        import io

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text and text.strip():
                pages.append(text.strip())
        return "\n\n".join(pages)
