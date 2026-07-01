"""Split text into chunks using LangChain text splitters."""

from __future__ import annotations


class TextChunker:
    """Split text into overlapping chunks for embedding.

    Uses LangChain's RecursiveCharacterTextSplitter under the hood.
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk(self, text: str) -> list[str]:
        """Split text into chunks.

        Args:
            text: Input text to split.

        Returns:
            List of text chunks.
        """
        if not text or not text.strip():
            return []

        try:
            from langchain_text_splitters import RecursiveCharacterTextSplitter

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=["\n\n", "\n", ". ", " ", ""],
            )
            return splitter.split_text(text)
        except (ImportError, ModuleNotFoundError):
            # Fallback: simple character-based splitting
            return self._simple_chunk(text)

    def _simple_chunk(self, text: str) -> list[str]:
        """Simple character-based chunking fallback."""
        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self.chunk_size, len(text))
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap
        return chunks

    def chunk_with_metadata(
        self,
        text: str,
        source_type: str = "manual",
        file_name: str | None = None,
    ) -> list[tuple[str, dict]]:
        """Split text and attach metadata to each chunk.

        Args:
            text: Input text to split.
            source_type: 'manual' or 'file'.
            file_name: Original file name (for file sources).

        Returns:
            List of (chunk_text, metadata_dict) tuples.
        """
        chunks = self.chunk(text)
        result = []
        for i, chunk_text in enumerate(chunks):
            meta: dict = {
                "source_type": source_type,
                "chunk_index": i,
            }
            if file_name is not None:
                meta["file_name"] = file_name
            result.append((chunk_text, meta))
        return result
