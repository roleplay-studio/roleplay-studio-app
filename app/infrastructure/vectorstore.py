"""Chroma knowledge-base adapters.

Supports runtime disable via empty embedding_model.
When disabled, all CRUD and search methods return empty/no-op results.
"""

import asyncio
from collections import OrderedDict
from typing import Any, cast

from langchain_chroma import Chroma

from app.application.dto import AddKnowledgeEntryCommand, KnowledgeEntryDTO
from app.infrastructure.config import Settings
from app.infrastructure.embeddings import HttpEmbeddings


class ChromaKnowledgeBase:
    """Vector-store backed knowledge base using ChromaDB.

    When embedding_model is empty/unset in Settings, the knowledge base
    operates in NO-OP mode — all methods return empty results without
    touching Chroma or any external API. This allows users to completely
    disable RAG without removing knowledge base entries.
    """

    MAX_VECTORSTORES = 128

    def __init__(self, persist_directory: str | None = None, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        # ``effective_chroma_persist_dir`` is absolute; relative
        # ``chroma_persist_dir`` from .env is resolved against the data
        # dir at access time.
        self.persist_directory = persist_directory or str(
            self.settings.effective_chroma_persist_dir
        )
        self._embeddings: HttpEmbeddings | None = None
        self._vectorstores: OrderedDict[int, Chroma] = OrderedDict()
        self._initialized: dict[int, bool] = {}
        self._stale_bots: set[int] = set()

    @property
    def embedding_enabled(self) -> bool:
        """True if an embedding model is configured and embeddings can be computed."""
        model = self.settings.embedding_model
        return bool(model and model.strip())

    def _current_fingerprint(self) -> str:
        """SHA256 of (embedding_model + embedding_base_url + api_key_hash).

        Stored in each Chroma collection's metadata. When the stored fingerprint
        doesn't match the current one, the collection is marked stale and the
        reindex flow kicks in.
        """
        import hashlib

        # Unwrap SecretStr to its raw value for the hash (m15). An
        # explicit ``None`` (no-auth local server) hashes as the empty
        # string — different from an unset key, which after M13 is
        # also ``None``. That's fine: we only need a stable token to
        # detect drift; we don't need a cryptographic comparison.
        raw_key = self.settings.embedding_api_key
        key_str = raw_key.get_secret_value() if raw_key is not None else ""
        key_hash = hashlib.sha256(key_str.encode()).hexdigest()[:16]
        # M13: use the effective URL (with LLM fallback) so the
        # fingerprint matches the URL the embedding client actually
        # hits.
        raw = (
            f"{self.settings.embedding_model}|"
            f"{self.settings.effective_embedding_base_url}|"
            f"{key_hash}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def is_stale(self, bot_id: int) -> bool:
        """True if this bot's collection was built with a different embedding config."""
        return bot_id in self._stale_bots

    @property
    def stale_bot_ids(self) -> set[int]:
        return set(self._stale_bots)

    def _get_embeddings(self) -> HttpEmbeddings:
        if self._embeddings is None:
            self._embeddings = HttpEmbeddings(self.settings)
        return self._embeddings

    def _collection_name(self, bot_id: int) -> str:
        return f"{self.settings.chroma_collection_prefix}{bot_id}"

    def _get_vectorstore(self, bot_id: int) -> Chroma:
        if not self.embedding_enabled:
            raise RuntimeError(
                "Embeddings are disabled (embedding_model is empty). "
                "Set EMBEDDING_MODEL in .env or via settings."
            )

        if bot_id in self._vectorstores:
            self._vectorstores.move_to_end(bot_id)
            return self._vectorstores[bot_id]

        vs = Chroma(
            persist_directory=self.persist_directory,
            embedding_function=cast(Any, self._get_embeddings()),
            collection_name=self._collection_name(bot_id),
        )

        # Fingerprint check — mark stale if model/url/key changed
        try:
            metadata = vs._collection.metadata or {}
            stored_fp = metadata.get("embedding_fingerprint")
            current_fp = self._current_fingerprint()
            if stored_fp is None:
                # Legacy collection — backfill
                vs._collection.modify(metadata={**metadata, "embedding_fingerprint": current_fp})
            elif stored_fp != current_fp:
                self._stale_bots.add(bot_id)
        except Exception:
            # If metadata read fails, treat as stale to be safe
            self._stale_bots.add(bot_id)

        if len(self._vectorstores) >= self.MAX_VECTORSTORES:
            self._vectorstores.popitem(last=False)
        self._vectorstores[bot_id] = vs
        self._initialized[bot_id] = True
        return vs

    def initialize(self, bot_id: int) -> None:
        """Ensure a Chroma collection exists for *bot_id*."""
        if not self.embedding_enabled:
            return
        self._get_vectorstore(bot_id)

    def add(self, command: AddKnowledgeEntryCommand) -> None:
        if not self.embedding_enabled:
            return
        self.add_texts(command.bot_id, [command.content], [command.metadata])

    def add_texts(
        self,
        bot_id: int,
        texts: list[str],
        metadatas: list[dict[str, Any]] | None = None,
    ) -> None:
        if not self.embedding_enabled:
            return
        if bot_id in self._stale_bots:
            self._rebuild_collection(bot_id)
            self._stale_bots.discard(bot_id)
        try:
            self._get_vectorstore(bot_id).add_texts(
                texts=texts,
                metadatas=metadatas or [{} for _ in texts],
            )
        except Exception as exc:
            detail = str(exc)
            if "embedding with dimension" in detail and "got" in detail:
                # Embedding model changed — rebuild collection and retry
                self._rebuild_collection(bot_id)
                self._get_vectorstore(bot_id).add_texts(
                    texts=texts,
                    metadatas=metadatas or [{} for _ in texts],
                )
            else:
                raise

    def search(self, bot_id: int, query: str, top_k: int = 15) -> list[str]:
        if not self.embedding_enabled:
            return []
        if bot_id in self._stale_bots:
            return []  # Degraded mode: don't return semantically-broken results
        vectorstore = self._get_vectorstore(bot_id)
        threshold = self.settings.knowledge_relevance_threshold
        results = vectorstore.similarity_search_with_score(query=query, k=top_k)
        return [doc.page_content for doc, dist in results if self._l2sq_to_score(dist) >= threshold]

    def search_with_scores(
        self, bot_id: int, query: str, top_k: int = 15
    ) -> list[tuple[str, float]]:
        """Search and return (content, relevance_score) pairs, unfiltered.
        Used by the test-search UI to show raw similarity scores."""
        if not self.embedding_enabled:
            return []
        vectorstore = self._get_vectorstore(bot_id)
        results = vectorstore.similarity_search_with_score(query=query, k=top_k)
        return [(doc.page_content, round(self._l2sq_to_score(dist), 4)) for doc, dist in results]

    @staticmethod
    def _l2sq_to_score(dist: float) -> float:
        """Convert Chroma's squared-L2 distance to a cosine-similarity score in [0, 1].

        Chroma with default (cosine) metric stores unit-normalized vectors and
        returns squared L2 distance: d² = ‖a-b‖² = 2 - 2·cos(a,b).
        So cosine_sim = 1 - d²/2, clamped to [0, 1].
        """
        return max(0.0, 1.0 - dist / 2.0)

    def list_entries(self, bot_id: int) -> list[KnowledgeEntryDTO]:
        if not self.embedding_enabled:
            return []
        if not self._initialized.get(bot_id):
            return []
        vectorstore = self._get_vectorstore(bot_id)
        results = vectorstore.get(include=["documents", "metadatas"])
        documents = results.get("documents", []) or []
        metadatas = results.get("metadatas", []) or []
        entries = []
        for index, doc_id in enumerate(results.get("ids", []) or []):
            meta = metadatas[index] if index < len(metadatas) else None
            if meta is None:
                meta = {}
            entries.append(
                KnowledgeEntryDTO(
                    id=doc_id,
                    content=documents[index] if index < len(documents) else "",
                    source_type=meta.get("source_type", "manual"),
                    file_name=meta.get("file_name"),
                )
            )
        return entries

    def update(self, bot_id: int, entry_id: str, content: str) -> None:
        """Update a knowledge entry by re-embedding with new content."""
        if not self.embedding_enabled:
            return
        if not self._initialized.get(bot_id):
            return
        vs = self._get_vectorstore(bot_id)
        try:
            vs._collection.update(ids=[entry_id], documents=[content])
        except Exception as exc:
            detail = str(exc)
            if "embedding with dimension" in detail and "got" in detail:
                # Embedding model changed — rebuild collection with updated content
                old_entries = self.list_entries(bot_id)
                updated_contents = [content if e.id == entry_id else e.content for e in old_entries]
                self.delete_collection(bot_id)
                self.initialize(bot_id)
                if updated_contents:
                    self.add_texts(bot_id, updated_contents, [{} for _ in updated_contents])
            else:
                raise

    def delete(self, bot_id: int, entry_id: str) -> None:
        if not self.embedding_enabled:
            return
        if not self._initialized.get(bot_id):
            return
        self._get_vectorstore(bot_id).delete(ids=[entry_id])

    def delete_collection(self, bot_id: int) -> None:
        if not self.embedding_enabled:
            return
        if bot_id in self._vectorstores:
            self._vectorstores[bot_id].delete_collection()
            del self._vectorstores[bot_id]
            self._initialized.pop(bot_id, None)

    def get_entries(self, bot_id: int) -> list[dict]:
        """Return knowledge-base entries as plain dicts (compatibility API)."""
        return [entry.model_dump() for entry in self.list_entries(bot_id)]

    def _rebuild_collection(self, bot_id: int) -> None:
        """Delete and recreate a Chroma collection, keeping existing entries."""
        # Read existing entries before deleting
        old_entries = self.list_entries(bot_id)
        # Delete the old collection
        self.delete_collection(bot_id)
        # Recreate with current embedding model
        self.initialize(bot_id)
        # Re-add all entries
        if old_entries:
            self.add_texts(
                bot_id,
                [e.content for e in old_entries],
                [{} for _ in old_entries],
            )

    def delete_entry(self, bot_id: int, entry_id: str) -> None:
        """Alias for delete (compatibility API)."""
        self.delete(bot_id, entry_id)

    # ── Reindex ──────────────────────────────────────────────────────────────

    def reindex_all(self) -> dict[str, int]:
        """Wipe all Chroma collections and return stats.

        Safe to call even when embeddings are disabled — in that case
        it just clears the local caches and returns zero collections.
        Returns a dict with 'collections_removed' count.
        """
        count = 0
        # Collect all known bot IDs from vectorstores + initialized cache
        known_ids: set[int] = set(self._vectorstores.keys()) | set(self._initialized.keys())

        for bot_id in known_ids:
            try:
                if bot_id in self._vectorstores:
                    self._vectorstores[bot_id].delete_collection()
                elif self.embedding_enabled:
                    # Collection exists on disk but isn't cached — re-init then nuke
                    vs = self._get_vectorstore(bot_id)
                    vs.delete_collection()
                count += 1
            except Exception:
                pass  # Best-effort; collection may not exist on disk

        # Also nuke the persist directory for a clean slate
        import shutil

        try:
            shutil.rmtree(self.persist_directory, ignore_errors=True)
        except Exception:
            pass

        self._vectorstores.clear()
        self._initialized.clear()
        return {"collections_removed": count}

    # ── Stale-collection scanning ────────────────────────────────────────────

    def scan_for_stale_collections(self, known_bot_ids: list[int] | None = None) -> list[int]:
        """Iterate known bot IDs (or scan disk if not provided) and return
        those whose stored fingerprint doesn't match the current one.

        Populates self._stale_bots as a side effect.
        """
        if not self.embedding_enabled:
            return []

        if known_bot_ids is None:
            known_bot_ids = self._list_bot_ids_on_disk()

        for bot_id in known_bot_ids:
            try:
                self._get_vectorstore(bot_id)  # populates _stale_bots
            except Exception:
                pass
        return sorted(self._stale_bots)

    def _list_bot_ids_on_disk(self) -> list[int]:
        """Discover bot IDs by scanning Chroma persist directory for kb_bot_* subdirs."""
        from pathlib import Path

        prefix = self.settings.chroma_collection_prefix
        base = Path(self.persist_directory)
        if not base.exists():
            return []
        ids: list[int] = []
        for sub in base.iterdir():
            if sub.is_dir() and sub.name.startswith(prefix):
                try:
                    ids.append(int(sub.name.removeprefix(prefix)))
                except ValueError:
                    continue
        return ids


class AsyncChromaKnowledgeBase:
    """Async application adapter over the synchronous Chroma implementation.

    Chroma and the embedding HTTP client are blocking. Keep the compatibility
    API synchronous, but never run those calls directly on the FastAPI event loop.
    """

    def __init__(self, sync_store: ChromaKnowledgeBase):
        self._sync_store = sync_store
        self._lock = asyncio.Lock()

    async def add(self, command: AddKnowledgeEntryCommand) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_store.add, command)

    async def search(self, bot_id: int, query: str, top_k: int = 3) -> list[str]:
        async with self._lock:
            return await asyncio.to_thread(self._sync_store.search, bot_id, query, top_k)

    async def search_with_scores(
        self, bot_id: int, query: str, top_k: int = 5
    ) -> list[tuple[str, float]]:
        async with self._lock:
            return await asyncio.to_thread(
                self._sync_store.search_with_scores, bot_id, query, top_k
            )

    async def list_entries(self, bot_id: int) -> list[KnowledgeEntryDTO]:
        async with self._lock:
            return await asyncio.to_thread(self._sync_store.list_entries, bot_id)

    async def delete(self, bot_id: int, entry_id: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_store.delete, bot_id, entry_id)

    async def update(self, bot_id: int, entry_id: str, content: str) -> None:
        async with self._lock:
            await asyncio.to_thread(self._sync_store.update, bot_id, entry_id, content)
