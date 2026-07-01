"""Summarize messages and threads using the fast/cheap LLM."""

import asyncio
import logging
from collections.abc import Callable

from app.application.dto import MessageDTO
from app.application.ports import LLMPort, MessageRepository
from app.infrastructure.config import Settings

logger = logging.getLogger(__name__)

SHORT_CONTENT_PROMPT = (
    "Summarize the following message in 5-15 words. "
    "Capture the key point or action. Respond with ONLY the summary, no quotes. "
    "Do NOT include reasoning, thinking, or analysis. Use original message language."
)

THREAD_SUMMARY_PROMPT = (
    "You are a summarization assistant. Summarize the given fictional narrative in a single, very short and concise statement of fact."
    "Write a brief 2-3 sentence summary of what's currently happening in the story."
    "Include names when possible."
    "Response must be in the past tense."
    "Your response must ONLY contain the summary."
    "Use original message language."
)


class MessageSummarizer:
    """Generates short_content for messages and summary for threads using fast LLM."""

    def __init__(
        self,
        llm: LLMPort,
        messages: MessageRepository,
        settings: Settings | None = None,
    ):
        self._llm = llm
        self._messages = messages
        # M10: ``Settings`` is now injected at construction, matching
        # the pattern used by ``ChatService`` (K3 fix), the
        # orchestrator (M4), and ``OpenRouterLLM``. Previously this
        # class called ``Settings.from_env()`` inside ``summarize_message``
        # and ``batch_summarize`` — meaning the summarizer could
        # disagree with the orchestrator / LLM / chat service about
        # ``summarize_max_tokens`` and ``summarize_min_length`` if the
        # env changed between calls. Tests and ``bootstrap.py`` pass
        # an explicit instance; default = ``Settings.from_env()`` for
        # ad-hoc construction.
        self._settings: Settings = settings or Settings.from_env()

    async def summarize_message(self, message_id: int, content: str) -> str | None:
        """Generate a short summary of a single message and save it.

        Respects summarize_min_length and summarize_max_tokens settings.
        """
        if not content:
            return None

        # M10: use the injected settings rather than re-reading the
        # env on every call (see __init__ docstring for context).
        settings = self._settings

        # Skip short messages — they don't need summarization
        if len(content) < settings.summarize_min_length:
            return None

        try:
            short = await self._llm.generate_response(
                [
                    {
                        "role": "system",
                        "content": "You are a concise summarizer. Output only the summary, nothing else.",
                    },
                    {
                        "role": "user",
                        "content": f"{SHORT_CONTENT_PROMPT}\n\nMessage: {content[:2000]}",
                    },
                ],
                temperature=0.3,
                max_tokens=settings.summarize_max_tokens,
            )
            short = short.strip().strip('"').strip("'").strip("«»").strip()
            if short:
                await self._messages.update_short_content(message_id, short)
                return short
        except asyncio.CancelledError:
            # m7: honour cancellation (re-raise). Otherwise the
            # caller's awaitable would silently return None and
            # the abort endpoint would think summarization
            # succeeded. asyncio.CancelledError is a
            # BaseException (not Exception) since Python 3.8, so
            # the broad ``except Exception:`` below wouldn't catch
            # it — the explicit re-raise block is required.
            raise
        except Exception:
            # Broad catch covers httpx, sqlalchemy, LLM provider
            # errors uniformly. Tracked as m7 in docs/review.md.
            logger.exception("Failed to summarize message %d", message_id)

        return None

    async def summarize_thread_recent(
        self,
        thread_id: int,
        recent_messages: list[MessageDTO],
        on_summary_ready: Callable[[int, str], None] | None = None,
    ) -> str | None:
        """Generate a thread-level summary from recent short_content entries.

        Uses the short_content of recent messages (or their full content
        if short_content is not yet set) to produce a compact plot summary.
        """
        if not recent_messages:
            return None

        # Collect short summaries from recent messages
        snippets: list[str] = []
        for msg in recent_messages[-10:]:  # last 10 messages max
            text = msg.short_content or msg.content[:500]
            role_label = "👤" if msg.role == "user" else "🤖"
            snippets.append(f"{role_label} {text}")

        if not snippets:
            return None

        history_text = "\n".join(snippets)
        try:
            summary = await self._llm.generate_response(
                [
                    {
                        "role": "system",
                        "content": "You are a concise story summarizer. Output only the summary, nothing else.",
                    },
                    {
                        "role": "user",
                        "content": f"{THREAD_SUMMARY_PROMPT}\n\nRecent messages:\n{history_text}",
                    },
                ],
                temperature=0.3,
                max_tokens=300,
            )
            summary = summary.strip().strip('"').strip("'").strip("«»").strip()
            if not summary:
                logger.warning("LLM returned empty summary for thread %d", thread_id)
                return None
            if on_summary_ready:
                on_summary_ready(thread_id, summary)
            return summary
        except asyncio.CancelledError:
            # m7: see summarize_message — re-raise so callers can
            # honour cancellation.
            raise
        except Exception:
            logger.exception("Failed to summarize thread %d", thread_id)

        return None

    async def batch_summarize(
        self,
        items: list[tuple[int, str]],
        max_concurrent: int = 3,
    ) -> dict[int, str | None]:
        """Summarize multiple messages concurrently.

        Args:
            items: List of (message_id, content) tuples.
            max_concurrent: Maximum parallel LLM requests.

        Returns:
            Dict mapping message_id -> summary (or None on failure).
        """
        if not items:
            return {}

        # M10: use the injected settings (see __init__ docstring).
        settings = self._settings
        results: dict[int, str | None] = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _summarize_one(msg_id: int, content: str) -> tuple[int, str | None]:
            async with semaphore:
                try:
                    short = await self._llm.generate_response(
                        [
                            {
                                "role": "system",
                                "content": "You are a concise summarizer. Output only the summary, nothing else.",
                            },
                            {
                                "role": "user",
                                "content": f"{SHORT_CONTENT_PROMPT}\n\nMessage: {content[:2000]}",
                            },
                        ],
                        temperature=0.3,
                        max_tokens=settings.summarize_max_tokens,
                    )
                    short = short.strip().strip('"').strip("'").strip("«»").strip()
                    if short:
                        await self._messages.update_short_content(msg_id, short)
                        return msg_id, short
                    return msg_id, None
                except asyncio.CancelledError:
                    # m7: same pattern — re-raise so the outer
                    # ``asyncio.gather`` (with return_exceptions=True)
                    # sees the cancellation. The outer caller can
                    # then decide whether to abort the whole batch
                    # or continue with the rest.
                    raise
                except Exception:
                    logger.exception("Failed to batch-summarize message %d", msg_id)
                    return msg_id, None

        # Filter out messages that are too short
        tasks = []
        for msg_id, content in items:
            if not content:
                continue
            if len(content) < settings.summarize_min_length:
                continue
            tasks.append(_summarize_one(msg_id, content))

        if not tasks:
            return {}

        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for item in completed:
            if isinstance(item, BaseException):
                # M-review2: ``asyncio.gather(return_exceptions=True)``
                # wraps every exception — including ``CancelledError`` —
                # into a result slot. Logging it and continuing breaks
                # the cancellation contract: a cancelled batch task
                # must propagate so the caller (e.g. abort endpoint)
                # can honour the cancellation. Re-raise so the caller's
                # ``except CancelledError`` fires.
                if isinstance(item, asyncio.CancelledError):
                    raise item
                logger.error("Batch summarize task failed: %s", item)
                continue
            msg_id, summary = item
            results[msg_id] = summary

        return results
