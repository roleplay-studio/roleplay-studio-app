"""Background reindex service for embedding model changes."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from app.infrastructure.vectorstore import ChromaKnowledgeBase


def _content_id(content: str, bot_id: int) -> str:
    """SHA256-based content-hash ID for idempotent re-adds."""
    return hashlib.sha256(f"{bot_id}|{content}".encode()).hexdigest()[:32]


@dataclass
class ReindexJob:
    job_id: str
    status: Literal["pending", "running", "completed", "failed", "cancelled"] = "pending"
    total_bots: int = 0
    bots_done: int = 0
    current_bot_id: int | None = None
    current_bot_name: str | None = None
    current_bot_entries_total: int = 0
    current_bot_entries_done: int = 0
    error: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "total_bots": self.total_bots,
            "bots_done": self.bots_done,
            "current_bot_id": self.current_bot_id,
            "current_bot_name": self.current_bot_name,
            "current_bot_entries_total": self.current_bot_entries_total,
            "current_bot_entries_done": self.current_bot_entries_done,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }


class ReindexService:
    """Owns ReindexJob lifecycle. Single in-flight job (concurrent = 409)."""

    def __init__(self) -> None:
        self._jobs: dict[str, ReindexJob] = {}
        self._cancel_flags: dict[str, asyncio.Event] = {}
        self._running_job_id: str | None = None
        self._lock = asyncio.Lock()
        self._worker_task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        return self._running_job_id is not None

    @property
    def running_job_id(self) -> str | None:
        return self._running_job_id

    async def start(self, kb: ChromaKnowledgeBase, bot_ids: list[int]) -> ReindexJob:
        """Start a reindex job. Raises RuntimeError if another is running."""
        async with self._lock:
            if self._running_job_id is not None:
                raise RuntimeError(f"Reindex already running (job_id={self._running_job_id})")
            job = ReindexJob(
                job_id=str(uuid.uuid4()),
                total_bots=len(bot_ids),
            )
            self._jobs[job.job_id] = job
            self._running_job_id = job.job_id
            cancel_event = asyncio.Event()
            self._cancel_flags[job.job_id] = cancel_event
            self._worker_task = asyncio.create_task(self._worker(kb, job, bot_ids, cancel_event))
            return job

    def cancel(self, job_id: str) -> bool:
        """Signal cancellation. Returns False if job is not running."""
        event = self._cancel_flags.get(job_id)
        if event:
            event.set()
            return True
        return False

    def get(self, job_id: str) -> ReindexJob | None:
        return self._jobs.get(job_id)

    async def _worker(
        self,
        kb: ChromaKnowledgeBase,
        job: ReindexJob,
        bot_ids: list[int],
        cancel: asyncio.Event,
    ) -> None:
        job.status = "running"
        try:
            for bot_id in bot_ids:
                if cancel.is_set():
                    job.status = "cancelled"
                    return
                await asyncio.to_thread(self._reindex_one_bot, kb, job, bot_id)
                job.bots_done += 1
            job.status = "completed"
        except Exception as e:
            job.status = "failed"
            job.error = str(e)
        finally:
            job.finished_at = datetime.now(UTC)
            self._running_job_id = None

    def _reindex_one_bot(self, kb: ChromaKnowledgeBase, job: ReindexJob, bot_id: int) -> None:
        """Re-embed a single bot's collection. Updates job progress."""
        entries = kb.list_entries(bot_id)
        job.current_bot_id = bot_id
        job.current_bot_entries_total = len(entries)
        job.current_bot_entries_done = 0

        if not entries:
            return

        contents = [e.content for e in entries]
        metadatas = [{"source_type": e.source_type} for e in entries]

        # Delete old, add new with content-hash IDs (idempotent on re-run)
        kb.delete_collection(bot_id)
        kb.initialize(bot_id)

        # Batch add with progress
        batch_size = 16
        for i in range(0, len(contents), batch_size):
            batch_contents = contents[i : i + batch_size]
            batch_meta = metadatas[i : i + batch_size]
            kb.add_texts(bot_id, batch_contents, batch_meta)
            job.current_bot_entries_done = min(i + batch_size, len(contents))
