import json
import logging
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Literal, cast

from app.application.dto import (
    ExportMessageDTO,
    ImportChatResponse,
    MessageDTO,
    RecentThreadDTO,
    ThreadDTO,
    ThreadStatsDTO,
)
from app.application.exceptions import NotFoundError
from app.application.ports import BotRepository, MessageRepository, ThreadRepository

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ThreadService:
    def __init__(
        self,
        threads: ThreadRepository,
        messages: MessageRepository,
        bots: BotRepository | None = None,
    ):
        self._threads = threads
        self._messages = messages
        self._bots = bots  # optional — only needed for set_first_message

    async def set_first_message(self, thread_id: int, bot_id: int, greeting_index: int) -> None:
        """Overwrite the first assistant message of a thread with the chosen greeting.

        ``greeting_index`` is the position in ``[bot.first_message, *bot.alternate_greetings]``.
        If the thread has no assistant message yet, the chosen content is stored
        as the thread's pending greeting so the next first_message save picks it up.
        """
        if self._bots is None:
            raise NotFoundError("BotRepository is not wired into ThreadService")

        bot = await self._bots.get(bot_id)
        if bot is None:
            raise NotFoundError(f"Bot {bot_id} not found")

        alt_raw = getattr(bot, "alternate_greetings", []) or []
        alt_list: list[str] = []
        if isinstance(alt_raw, str):
            try:
                parsed = json.loads(alt_raw)
                alt_list = parsed if isinstance(parsed, list) else []
            except (TypeError, ValueError):
                alt_list = []
        elif isinstance(alt_raw, list):
            alt_list = alt_raw

        greetings: list[str] = [bot.first_message, *alt_list]
        if greeting_index < 0 or greeting_index >= len(greetings):
            raise ValueError(
                f"greeting_index {greeting_index} out of range (0..{len(greetings) - 1})"
            )
        chosen = greetings[greeting_index]

        first_asst = await self._messages.get_first_assistant(thread_id)
        if first_asst is None:
            await self._threads.set_pending_greeting(thread_id, chosen)
            return
        if first_asst.id is None:
            raise NotFoundError(f"First assistant message in thread {thread_id} has no id")
        await self._messages.update_content(first_asst.id, chosen)

    async def create_thread(
        self,
        bot_id: int,
        name: str = "new chat",
        persona_id: int | None = None,
        parent_thread_id: int | None = None,
    ) -> int:
        thread_id = await self._threads.create(
            bot_id,
            name.strip() or "new chat",
            persona_id=persona_id,
            parent_thread_id=parent_thread_id,
        )
        if persona_id is not None:
            await self._threads.set_persona(thread_id, persona_id)
        return thread_id

    async def get_thread(self, thread_id: int) -> ThreadDTO:
        thread = await self._threads.get(thread_id)
        if thread is None:
            raise NotFoundError(f"Thread {thread_id} was not found")
        return thread

    async def list_threads(self, bot_id: int) -> list[ThreadDTO]:
        """List threads for a bot — enriched with preview fields.

        Delegates to the repository's ``list_for_bot_with_preview`` so
        the chat thread-list UI gets the message_count + last-message
        metadata in one round-trip instead of firing N+1
        ``GET /api/threads/{id}/stats`` calls. See ThreadDTO field
        docs for the contract.
        """
        return await self._threads.list_for_bot_with_preview(bot_id)

    async def list_recent_threads(
        self,
        limit: int = 20,
        bot_id: int | None = None,
        before_thread_id: int | None = None,
    ) -> list[RecentThreadDTO]:
        """Cross-bot recent listing, enriched with preview fields + count.

        ``before_thread_id`` enables keyset pagination — pass the id of
        the last thread in the previous page and you'll get the next
        page older than it. See :meth:`ThreadRepository.list_recent_with_previews`
        for the SQL semantics.
        """
        return await self._threads.list_recent_with_previews(
            limit=limit,
            bot_id=bot_id,
            before_thread_id=before_thread_id,
        )

    async def rename_thread(self, thread_id: int, name: str) -> None:
        await self._threads.rename(thread_id, name.strip())

    async def update_thread_summary(self, thread_id: int, summary: str) -> None:
        await self._threads.update_summary(thread_id, summary)

    async def delete_thread(self, thread_id: int) -> None:
        await self._threads.delete(thread_id)

    async def set_thread_persona(self, thread_id: int, persona_id: int | None) -> None:
        await self._threads.set_persona(thread_id, persona_id)

    async def find_by_bot_and_persona(self, bot_id: int, persona_id: int) -> ThreadDTO | None:
        return await self._threads.find_by_bot_and_persona(bot_id, persona_id)

    async def clear_conversation(self, thread_id: int) -> None:
        await self._messages.clear_thread(thread_id)

    async def list_messages(
        self,
        thread_id: int,
        limit: int = 20,
        before_id: int | None = None,
    ) -> list[MessageDTO]:
        """Return active messages for ``thread_id``.

        Args:
            thread_id: Chat thread id.
            limit: Maximum number of messages to return (newest first).
            before_id: Optional cursor — when set, only messages with a
                strictly smaller id are returned, enabling keyset
                pagination for long chats.

        The repository may attach alternate ``branch_group`` versions
        to messages that have them.
        """
        return await self._messages.list_for_thread(thread_id, limit, before_id=before_id)

    async def get_stats(self, thread_id: int) -> ThreadStatsDTO:
        """Return header-level stats for the thread.

        Complements the paginated ``list_messages`` so the chat header
        can show the **real** message total (not just the latest
        50-message window). The token estimate mirrors the frontend's
        ``chars / 4`` ceiling — it is intentionally cheap and matches
        the visible counter.

        Raises ``NotFoundError`` only if the thread itself does not
        exist; an empty thread returns zero-count stats instead of an
        error.
        """
        # Confirm the thread exists so we don't accidentally return
        # stats for a stale / deleted thread id (e.g. after the user
        # clears their chat). Empty thread -> 0 messages -> header
        # shows "0 msgs".
        thread = await self._threads.get(thread_id)
        if thread is None:
            raise NotFoundError(f"Thread {thread_id} not found")

        active = await self._messages.list_for_thread(thread_id, limit=10_000)
        chars = sum(len(m.content) for m in active)
        return ThreadStatsDTO(
            thread_id=thread_id,
            message_count=len(active),
            token_estimate=chars // 4,
        )

    async def save_assistant_message(self, thread_id: int, content: str) -> None:
        await self._messages.save(thread_id, "assistant", content)

    async def update_message(
        self,
        thread_id: int,
        message_id: int,
        content: str,
        state: str | None = None,
    ) -> int | None:
        """Edit a message, creating a new branch version.

        If the message has no branch group yet, the original is marked
        as branch version 0 (inactive) and the edited content becomes
        version 1 (active). The new version preserves the original
        message's timestamp so it stays in the same position in history.

        ``state`` controls the world-state snapshot on the new branch:
        ``None`` (default) copies the original's state — preserves
        branching fidelity so a user who edits an assistant message
        without touching the world state still sees the state they
        had in mind when they decided to edit. ``""`` explicitly
        clears the snapshot.

        Returns the new message id.
        """
        if not content.strip():
            return None

        # Get the original message's branch info
        versions = await self._messages.get_versions(message_id)
        next_index = 0
        original_state: str | None = None
        if versions:
            target = versions[0]  # original for role + timestamp + state
            branch_group = target.branch_group
            next_index = max(v.branch_index for v in versions) + 1
            original_state = target.state
            # Deactivate the previous active version before creating the new one
            old_active = next((v for v in versions if v.id == message_id), None)
            if old_active is not None and branch_group is not None:
                await self._messages.update_branch(
                    message_id, branch_group, old_active.branch_index, is_active=False
                )
        else:
            all_msgs = await self._messages.list_for_thread(thread_id, limit=200)
            target = next((m for m in all_msgs if m.id == message_id), None)
            if target is None:
                raise NotFoundError(f"Message {message_id} was not found in thread {thread_id}")
            branch_group = None
            original_state = target.state

        role = target.role
        original_timestamp = target.created_at

        if branch_group is None:
            # First edit — create a branch group
            branch_group = str(uuid.uuid4())
            await self._messages.update_branch(message_id, branch_group, 0, is_active=False)
            next_index = 1

        # ``None`` means "use the original message's state"; a string
        # (including ``""``) is the explicit new value. Without this
        # three-way contract, branching on a state-bearing assistant
        # message would silently drop the world-state context the
        # user was relying on when they decided to edit.
        effective_state = state if state is not None else original_state

        # Save the edited version as the new active branch
        new_id = await self._messages.save_branch(
            thread_id,
            role,
            content.strip(),
            branch_group,
            next_index,
            timestamp=original_timestamp,
            state=effective_state,
        )
        return new_id

    async def delete_message(self, message_id: int) -> None:
        await self._messages.delete(message_id)

    async def delete_message_cascade(self, thread_id: int, message_id: int) -> None:
        """Delete message_id and all messages after it."""
        await self._messages.delete_from(thread_id, message_id)

    async def get_versions(self, message_id: int) -> list[MessageDTO]:
        """Get all versions of a branched message."""
        return await self._messages.get_versions(message_id)

    async def switch_version(self, thread_id: int, message_id: int, target_version_id: int) -> None:
        """Switch to a different version of a branched message."""
        versions = await self._messages.get_versions(message_id)
        if not versions or versions[0].branch_group is None:
            raise NotFoundError(f"Message {message_id} has no branch versions")
        await self._messages.switch_version(versions[0].branch_group, target_version_id)

    async def fork_at_message(self, thread_id: int, message_id: int) -> int:
        """Create a new chat thread that snapshots the conversation up to
        ``message_id`` (inclusive), then return the new thread id.

        The user-facing flow: the user clicks a fork icon on a message
        in the chat UI, and the backend produces an independent
        ``ChatThread`` containing a copy of every active message from
        the source thread whose id is <= ``message_id``. The frontend
        redirects them to the new thread so they can continue chatting
        without affecting the original. The source thread is
        read-only — no rows are inserted, updated, or deleted on it.

        Implementation notes (correspond to the touchpoints in the
        test fixture / route layer):

        * **Active-chain filter** is applied by
          ``MessageRepository.list_active_until``, which mirrors the
          SQL filter of ``list_for_thread`` (rows with no
          ``branch_group`` plus the active row of any branch group).
          Diverging filters would silently drop messages the chat UI
          is showing — pitfall 6at.
        * **Branch groups collapse** to ``None`` on the copied rows
          because the new thread has no siblings to navigate to.
          Users who forked at a branched message expect a clean
          linear chain in the fork, not a stale version-switcher.
        * **Per-message metadata** (``state``, ``reasoning``,
          ``dynamic_system_prompt``, ``short_content``,
          ``generation_status``, original ``timestamp``) is copied
          verbatim so the fork renders identically to the source up
          to that point.
        * **Thread-level metadata** inherited from the source:
          ``bot_id``, ``persona_id``, ``summary``. The new thread's
          ``name`` is prefixed with ``"Fork of "`` so the sidebar
          makes the lineage obvious without forcing the user to
          rename it.
        * **Attached files (``ThreadFile``)** are NOT copied —
          they're bound to the original thread. The fork has its
          own upload context; carrying files across would create
          phantom attachments pointing at rows the user never
          explicitly added to the new thread.

        Raises:
            NotFoundError: source thread does not exist, or
                ``message_id`` doesn't belong to it. Both surface as
                404 at the route layer so the frontend can show a
                sensible error instead of creating an empty thread.
        """
        # 1. Pull the source thread so we can inherit bot_id /
        # persona_id / summary. Done BEFORE listing messages so the
        # "thread not found" error wins over "no messages" — that
        # ordering matters for the test suite's contract.
        source = await self._threads.get(thread_id)
        if source is None:
            raise NotFoundError(f"Thread {thread_id} was not found")

        # 2. Snapshot the active conversation up to and including
        # ``message_id``. Returns oldest-first, ready to persist.
        snapshot = await self._messages.list_active_until(
            thread_id=thread_id, until_message_id=message_id
        )
        if not snapshot:
            raise NotFoundError(
                f"Thread {thread_id} has no messages up to id {message_id}"
            )
        # 2a. Strict id-existence check — the ``list_active_until`` filter
        # is ``id <= until_message_id AND active-chain``, which is
        # silent-tolerant of a stale id (e.g. ``999999`` returns the
        # whole chain because every row passes the ``id <= 999999``
        # test). Without this guard the user would silently get a
        # "fork the entire thread" when they asked for a specific
        # message that doesn't exist — confusing UX and a data-
        # integrity footgun. The frontend always supplies the
        # message's own id, so a 404 here means the row was deleted
        # between list and fork (race) or the id was hand-crafted
        # (a test or a malicious client).
        if not any(m.id == message_id for m in snapshot):
            raise NotFoundError(
                f"Message {message_id} was not found in thread {thread_id}"
            )
        # 3. Create the new thread inheriting bot_id + persona_id.
        # The name carries the lineage marker; trimming the source
        # name keeps the sidebar readable when the source has a long
        # name like "Evening chat — Princess Lyra — Chapter 4".
        new_name = f"Fork of {source.name}".strip()
        new_thread_id = await self._threads.create(
            bot_id=source.bot_id,
            name=new_name,
            persona_id=source.persona_id,
            parent_thread_id=source.id,
        )

        # 4. Carry the source's persisted summary across. The
        # summary is bot-authored prose describing the plot so far —
        # forking from mid-conversation means the new thread starts
        # with the same narrative context.
        if source.summary:
            await self._threads.update_summary(new_thread_id, source.summary)

        # 5. Copy every message in the snapshot. ``save`` is the
        # linear insert path (no branch_group, is_active=True) — the
        # right semantics for a fresh thread that has no branch
        # history to navigate to.
        for msg in snapshot:
            if msg.id is None:
                # Defensive: the SQL repo always assigns ids; this
                # guards against future refactors where a synthetic
                # MessageDTO sneaks into the snapshot.
                continue
            await self._messages.save(
                thread_id=new_thread_id,
                role=msg.role,
                content=msg.content,
                # Branch groups collapse: the fork has no siblings
                # to navigate to, so we don't keep the link.
                branch_group=None,
                branch_index=0,
                is_active=True,
                short_content=msg.short_content,
                # Preserve the original timestamp so chronological
                # ordering matches what the user was looking at.
                timestamp=msg.created_at,
                generation_status=msg.generation_status,
                reasoning=msg.reasoning,
                # None on the source becomes None on the copy.
                # ``dynamic_system_prompt`` is the snapshot the LLM
                # saw; the user opens the fork expecting the same
                # floating-prompt panel.
                dynamic_system_prompt=msg.dynamic_system_prompt,
                # Same for world-state — copy verbatim so the
                # state-update task in the new thread starts from
                # the same world as the user saw when they hit
                # fork.
                state=msg.state,
            )

        return new_thread_id

    async def export_messages(self, thread_id: int) -> list[ExportMessageDTO]:
        """Export all messages for a thread (excludes system)."""
        messages = await self._messages.list_for_thread(thread_id, limit=10000)
        return [
            ExportMessageDTO(
                role=cast(Literal["user", "assistant"], str(msg.role)),
                content=msg.content,
                short_content=msg.short_content,
                created_at=msg.created_at.isoformat() if msg.created_at else None,
            )
            for msg in messages
            if msg.role != "system"
        ]

    async def import_chat(
        self,
        bot_id: int,
        file_content: bytes,
        persona_id: int | None = None,
    ) -> ImportChatResponse:
        """Import chat from JSON file — creates new thread with messages.

        Raises:
            ValueError: invalid JSON, empty array, missing fields.
            NotFoundError: bot not found.
        """
        # Parse JSON
        try:
            raw_messages = json.loads(file_content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON format: {e}") from e

        if not isinstance(raw_messages, list):
            raise ValueError("JSON must be a list of messages")
        if not raw_messages:
            raise ValueError("JSON array must not be empty")

        # Validate + convert
        validated: list[ExportMessageDTO] = []
        for i, msg in enumerate(raw_messages):
            if not isinstance(msg, dict):
                raise ValueError(f"Message {i}: must be a JSON object, got {type(msg).__name__}")
            role = msg.get("role")
            content = msg.get("content")
            if role not in ("user", "assistant"):
                raise ValueError(
                    f"Message {i}: invalid role '{role}', expected 'user' or 'assistant'"
                )
            if not content or not isinstance(content, str) or not content.strip():
                raise ValueError(f"Message {i}: 'content' must be a non-empty string")
            validated.append(
                ExportMessageDTO(
                    role=role,
                    content=content.strip(),
                    short_content=msg.get("short_content"),
                    created_at=msg.get("created_at"),
                )
            )

        # Create thread
        today = datetime.now().strftime("%d.%m.%Y")
        thread_id = await self.create_thread(
            bot_id, name=f"Import from {today}", persona_id=persona_id
        )

        # Bulk insert
        count = 0
        for msg in validated:
            timestamp = None
            if msg.created_at:
                try:
                    timestamp = datetime.fromisoformat(msg.created_at)
                except (ValueError, TypeError):
                    pass
            await self._messages.save(
                thread_id=thread_id,
                role=msg.role,
                content=msg.content,
                short_content=msg.short_content,
                timestamp=timestamp,
            )
            count += 1

        return ImportChatResponse(thread_id=thread_id, message_count=count)
