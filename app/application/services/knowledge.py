import logging

from app.application.dto import (
    AddKnowledgeEntryCommand,
    AddKnowledgeFileCommand,
    KnowledgeEntryDTO,
)
from app.application.ports import KnowledgeBaseRepository
from app.application.services.file_parser import FileParser
from app.application.services.text_chunker import TextChunker

logger = logging.getLogger(__name__)


class KnowledgeService:
    def __init__(
        self,
        knowledge: KnowledgeBaseRepository,
        chunker: TextChunker | None = None,
    ):
        self._knowledge = knowledge
        self._chunker = chunker or TextChunker()

    async def add_entry(self, command: AddKnowledgeEntryCommand) -> None:
        """Add a manual knowledge entry — chunk it first for better search."""
        chunks = self._chunker.chunk_with_metadata(
            command.content,
            source_type="manual",
        )
        for chunk_text, meta in chunks:
            entry_cmd = AddKnowledgeEntryCommand(
                bot_id=command.bot_id,
                content=chunk_text,
                metadata=meta,
            )
            await self._knowledge.add(entry_cmd)

    async def add_file(self, command: AddKnowledgeFileCommand) -> dict:
        """Upload and index a file.

        Parses the file, splits into chunks, and adds each chunk
        to the knowledge base with metadata.

        Returns:
            Dict with file_name, chunk_count, and status.
        """
        # 1. Parse file to text
        text = FileParser.parse(
            command.file_content,
            command.file_name,
            command.mime_type,
        )

        if not text.strip():
            return {"file_name": command.file_name, "chunk_count": 0, "status": "empty"}

        # 2. Split into chunks with metadata
        chunks = self._chunker.chunk_with_metadata(
            text,
            source_type="file",
            file_name=command.file_name,
        )

        # 3. Add each chunk to knowledge base
        for chunk_text, meta in chunks:
            entry_cmd = AddKnowledgeEntryCommand(
                bot_id=command.bot_id,
                content=chunk_text,
                metadata=meta,
            )
            await self._knowledge.add(entry_cmd)

        return {
            "file_name": command.file_name,
            "chunk_count": len(chunks),
            "status": "ok",
        }

    async def search(self, bot_id: int, query: str, top_k: int = 15) -> list[str]:
        return await self._knowledge.search(bot_id, query, top_k)

    async def test_search(
        self, bot_id: int, query: str, top_k: int = 15
    ) -> list[tuple[str, float]]:
        return await self._knowledge.search_with_scores(bot_id, query, top_k)

    async def list_entries(self, bot_id: int) -> list[KnowledgeEntryDTO]:
        return await self._knowledge.list_entries(bot_id)

    async def get_knowledge_contents(self, bot_id: int) -> list[str]:
        """Return just the content strings of a bot's knowledge entries.

        Used by the bot export endpoint to embed knowledge into a V2 character
        card's ``character_book.entries[*].content``. Empty and whitespace-only
        entries are filtered out — the V2 spec silently drops them and
        downstream consumers (Chroma vector index) reject them anyway.
        """
        entries = await self._knowledge.list_entries(bot_id)
        return [e.content for e in entries if e.content and e.content.strip()]

    async def update_entry(self, bot_id: int, entry_id: str, content: str) -> None:
        await self._knowledge.update(bot_id, entry_id, content)

    async def delete_entry(self, bot_id: int, entry_id: str) -> None:
        await self._knowledge.delete(bot_id, entry_id)

    async def delete_file_chunks(self, bot_id: int, file_name: str) -> int:
        """Delete all chunks belonging to a specific file.

        Returns:
            Number of deleted chunks.
        """
        entries = await self._knowledge.list_entries(bot_id)
        deleted = 0
        for entry in entries:
            # Check metadata in entry content or via a dedicated method
            if entry.file_name == file_name:
                await self._knowledge.delete(bot_id, entry.id)
                deleted += 1
        return deleted
