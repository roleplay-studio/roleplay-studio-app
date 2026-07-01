"""Tests for KnowledgeService.get_knowledge_contents (Task 1)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.application.dto import KnowledgeEntryDTO
from app.application.services.knowledge import KnowledgeService


@pytest.mark.asyncio
async def test_get_knowledge_contents_returns_list_of_strings() -> None:
    """Returns just the content strings for a bot's knowledge entries."""
    fake_entries = [
        KnowledgeEntryDTO(id="1", content="lore one", source_type="manual"),
        KnowledgeEntryDTO(id="2", content="lore two", source_type="manual"),
    ]
    repo = AsyncMock()
    repo.list_entries = AsyncMock(return_value=fake_entries)
    svc = KnowledgeService(repo)

    contents = await svc.get_knowledge_contents(bot_id=1)

    assert contents == ["lore one", "lore two"]
    repo.list_entries.assert_awaited_once_with(1)


@pytest.mark.asyncio
async def test_get_knowledge_contents_filters_empty_and_whitespace() -> None:
    """Empty / whitespace-only content is filtered out."""
    fake_entries = [
        KnowledgeEntryDTO(id="1", content="kept", source_type="manual"),
        KnowledgeEntryDTO(id="2", content="", source_type="manual"),
        KnowledgeEntryDTO(id="3", content="   ", source_type="manual"),
        KnowledgeEntryDTO(id="4", content="also kept", source_type="manual"),
    ]
    repo = AsyncMock()
    repo.list_entries = AsyncMock(return_value=fake_entries)
    svc = KnowledgeService(repo)

    contents = await svc.get_knowledge_contents(bot_id=42)

    assert contents == ["kept", "also kept"]
