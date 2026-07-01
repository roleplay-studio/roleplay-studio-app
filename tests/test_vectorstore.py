"""Tests for Chroma fingerprint detection and stale-collection handling.

These tests exercise the real langchain_chroma.Chroma (and underlying chromadb)
stack to verify that fingerprint metadata round-trips correctly. The conftest
mocks ``langchain_chroma`` at import time so that other tests don't pay the
import cost; we restore it here at module load time, then re-import the
vectorstore module so its ``Chroma`` binding points to the real class.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock

# --- Restore real langchain_chroma / langchain_core ------------------------
# conftest.py installs MagicMock stand-ins for these modules before any test
# file is imported. Strip them out (and any already-imported submodules) and
# let Python re-import the real ones, then reload the vectorstore module so
# its `from langchain_chroma import Chroma` resolves to the real class.
for _name in list(sys.modules):
    if (
        _name == "langchain_chroma"
        or _name == "langchain_core"
        or _name.startswith("langchain_core.")
    ):
        if isinstance(sys.modules[_name], MagicMock):
            del sys.modules[_name]

importlib.import_module("langchain_chroma")  # pre-warm so reload sees it

# If vectorstore was already imported under the mocked names, drop and reload.
if "app.infrastructure.vectorstore" in sys.modules:
    importlib.reload(sys.modules["app.infrastructure.vectorstore"])

# --- Now safe to import the SUT against the real Chroma --------------------
from app.infrastructure.config import Settings  # noqa: E402
from app.infrastructure.vectorstore import ChromaKnowledgeBase  # noqa: E402


def test_legacy_collection_backfills_fingerprint(tmp_path):
    """A collection created without metadata gets the fingerprint backfilled."""
    settings = Settings(
        embedding_model="bge-m3",
        embedding_base_url="http://localhost:11434/v1",
        embedding_api_key=None,
        chroma_persist_dir=str(tmp_path / "chroma"),
    )
    kb = ChromaKnowledgeBase(settings=settings)
    kb.initialize(bot_id=1)
    vs = kb._get_vectorstore(1)
    metadata = vs._collection.metadata or {}
    assert "embedding_fingerprint" in metadata
    assert metadata["embedding_fingerprint"] == kb._current_fingerprint()


def test_changing_embedding_model_marks_collection_stale(tmp_path):
    """After settings.embedding_model changes, initialize() marks the bot stale."""
    settings1 = Settings(
        embedding_model="model-v1",
        embedding_base_url="http://localhost:11434/v1",
        embedding_api_key=None,
        chroma_persist_dir=str(tmp_path / "chroma"),
    )
    kb1 = ChromaKnowledgeBase(settings=settings1)
    kb1.initialize(bot_id=1)
    assert kb1.is_stale(1) is False
    assert 1 not in kb1.stale_bot_ids

    settings2 = Settings(
        embedding_model="model-v2",
        embedding_base_url="http://localhost:11434/v1",
        embedding_api_key=None,
        chroma_persist_dir=str(tmp_path / "chroma"),
    )
    kb2 = ChromaKnowledgeBase(settings=settings2)
    kb2.initialize(bot_id=1)
    assert kb2.is_stale(1) is True
    assert 1 in kb2.stale_bot_ids


def test_stale_collection_search_returns_empty(tmp_path):
    """Search on a stale collection returns [] (degraded mode)."""
    settings1 = Settings(
        embedding_model="model-v1",
        embedding_base_url="http://localhost:11434/v1",
        embedding_api_key=None,
        chroma_persist_dir=str(tmp_path / "chroma"),
    )
    kb1 = ChromaKnowledgeBase(settings=settings1)
    kb1.initialize(bot_id=1)

    settings2 = Settings(
        embedding_model="model-v2",
        embedding_base_url="http://localhost:11434/v1",
        embedding_api_key=None,
        chroma_persist_dir=str(tmp_path / "chroma"),
    )
    kb2 = ChromaKnowledgeBase(settings=settings2)
    # Trigger the fingerprint check so the bot is marked stale.
    kb2.initialize(bot_id=1)
    assert kb2.is_stale(1) is True
    # Stale → search short-circuits to [] (no embedding API call).
    assert kb2.search(bot_id=1, query="test") == []
