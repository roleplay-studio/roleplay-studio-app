"""SQLAlchemy repository implementations — migrated to SQLModel.

SQLModel (sqlmodel>=0.0.22) combines SQLAlchemy 2.0 ORM + Pydantic v2,
eliminating the need for separate DTO ↔ ORM conversion methods
(e.g. _to_dto). The SQLModel classes in db/models.py are both the
table-definition and the Pydantic schema.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Literal, cast

from sqlalchemy import (
    delete as sa_delete,
)
from sqlalchemy import (
    func,
    select,
    text,
)
from sqlalchemy import (
    update as sa_update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.application.dto import (
    MessageDTO,
    RecentThreadDTO,
    ThreadDTO,
    ThreadFileDTO,
    UserPersonaDTO,
)
from app.application.exceptions import NotFoundError
from app.domain.enums import BotType
from app.infrastructure.config import Settings
from app.infrastructure.db.models import (
    AppSettings,
    Bot,
    BotVersion,
    ChatThread,
    Conversation,
    ThreadFile,
    UserPersona,
)

logger = logging.getLogger(__name__)


def _ensure_tz(dt: datetime) -> datetime:
    """If datetime is naive (timezone stripped by SQLite), assume UTC and attach timezone.

    M8 note: this is a defensive helper for the current SQLite-only
    deployment. SQLite doesn't have a native TZ-aware timestamp type
    (it's all ``TEXT`` under the hood), so SQLAlchemy strips the
    tzinfo on read. The right long-term fix is to migrate the
    ``created_at`` / ``updated_at`` / ``timestamp`` columns to
    ``TIMESTAMP WITH TIME ZONE`` (Postgres) or to
    ``sa_column=Column(DateTime(timezone=True))`` (cross-DB). Until
    that migration lands (tracked as M8 in docs/review.md), every
    read path that returns a datetime to the application must funnel
    through this helper.

    The default values in the SQLModel definitions are already
    ``datetime.now(UTC)`` (tz-aware), so the *write* path is fine —
    it's the *read* path that needs help. Don't remove this helper
    without auditing every place that consumes ``MessageDTO.timestamp``
    or any other datetime field.
    """
    if dt.tzinfo is None:
        # Logged at debug so the noise doesn't drown the real errors
        # but operators can opt in by setting LOG_LEVEL=DEBUG.
        logger.debug(
            "_ensure_tz: naive datetime %r encountered — assuming UTC. "
            "If you see this often, the M8 column migration is overdue.",
            dt,
        )
        return dt.replace(tzinfo=UTC)
    return dt


class SqlAlchemyStore:
    """Session factory and schema management backed by SQLModel.

    Uses SQLModel's `create_engine` (wraps SQLAlchemy's) and runs
    `SQLModel.metadata.create_all` for table creation.
    """

    def __init__(self, db_path: str | None = None, settings: Settings | None = None):
        self.settings = settings or Settings.from_env()
        # ``effective_db_path`` is absolute; relative ``db_path`` from
        # .env is resolved against the data dir at access time.
        self.db_path = db_path or str(self.settings.effective_db_path)
        engine_url = (
            self.db_path
            if self.db_path.startswith("sqlite+aiosqlite:///")
            else (
                f"sqlite+aiosqlite:///{self.db_path.removeprefix('sqlite:///')}"
                if self.db_path.startswith("sqlite:///")
                else f"sqlite+aiosqlite:///{self.db_path}"
            )
        )
        self._async_engine = create_async_engine(engine_url, echo=False)
        # SQLite doesn't enforce foreign keys by default — must opt in
        # per connection via PRAGMA. Without this, ``ON DELETE CASCADE``
        # on the bot_versions FK is silently ignored. event.listen on
        # the sync engine fires for each new DBAPI connection; the
        # async engine shares the same pool, so the PRAGMA is set
        # before any async session sees the connection.
        from sqlalchemy import event

        @event.listens_for(self._async_engine.sync_engine, "connect")
        def _enable_sqlite_fk(dbapi_conn, _record):
            cursor = dbapi_conn.cursor()
            try:
                cursor.execute("PRAGMA foreign_keys=ON")
            finally:
                cursor.close()

        self._async_session_factory = async_sessionmaker(
            self._async_engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self) -> None:
        """Apply all pending Alembic migrations.

        Schema management is delegated to Alembic (see ``alembic/`` and
        ``alembic.ini``). ``upgrade head`` is idempotent — running it on a
        freshly-stamped or up-to-date database is a no-op.

        We run the synchronous Alembic API in a worker thread so it doesn't
        conflict with the calling event loop (Alembic creates its own loop
        internally for async engines).

        m11: this method is safe to call repeatedly thanks to the
        ``_db_initialized`` guard below. The full fix (move the
        migration step into a dedicated init-container / k8s Job so
        ``SqlAlchemyStore.__init__`` is just a connection-pool
        factory) is tracked separately — it requires Docker /
        k8s deployment rewiring. For the current single-binary
        deployment the guard pattern is sufficient: a second call
        within the same process is a no-op.
        """
        import asyncio
        import sys
        from pathlib import Path

        from alembic.config import Config as AlembicConfig

        from alembic import command

        # m11: cheap re-entrancy guard. ``upgrade head`` itself is
        # idempotent, but this avoids the asyncio.to_thread spin-up
        # + config parsing + working-directory chdir on every call
        # when the app boots twice (e.g. ConversationManager
        # instantiated after bootstrap already called init_db).
        if getattr(self, "_db_initialized", False):
            logger.debug("init_db: already initialized, skipping")
            return

        # Locate alembic.ini regardless of the current working directory.
        # In dev: .../app/infrastructure/repositories/sqlalchemy.py → project root.
        # In a PyInstaller frozen bundle: data files declared in the spec's
        # `datas` list are stored under `<dest>/<basename(src)>/<basename(src)>`
        # in the bundle's `_internal/` (PyInstaller 6.x onedir layout). For
        # our entries the effective on-disk layout is:
        #   <meipass>/migrations/alembic.ini/alembic.ini
        #   <meipass>/migrations/alembic/{env.py,versions/...}
        # Routing alembic artifacts through `migrations/` (instead of the
        # root) avoids a name collision with the bundled ``alembic`` Python
        # package.
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            # Frozen: data files live under <meipass>/migrations/...
            migrations_root = Path(meipass) / "migrations"
            ini_path = migrations_root / "alembic.ini" / "alembic.ini"
            scripts_path = migrations_root / "alembic"
        else:
            # Dev: walk up from this file to the project root.
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            ini_path = project_root / "alembic.ini"
            scripts_path = project_root / "alembic"

        if not ini_path.exists():
            raise RuntimeError(f"alembic.ini not found at {ini_path}")

        cfg = AlembicConfig(str(ini_path))
        cfg.set_main_option("script_location", str(scripts_path))

        def _run() -> None:
            command.upgrade(cfg, "head")

        # Off-load to a thread so Alembic's internal event loop doesn't clash
        # with the one that's awaiting us.
        await asyncio.to_thread(_run)
        # m11: flip the guard *after* the actual work succeeded so
        # a failed init_db stays retriable on the next call.
        self._db_initialized = True

    async def health_check(self) -> None:
        """Round-trip a trivial query so the liveness probe can fail fast.

        Raises whatever the underlying driver raises on a broken connection
        (operational errors, ``OperationalError``, ``DatabaseError`` etc.) —
        the route layer converts those into a 503. Avoids alembic and any
        SQLModel metadata so it's safe to call before migrations have run.
        """
        from sqlalchemy import text

        async with self._async_session_factory() as s:
            await s.execute(text("SELECT 1"))

    async def session(self) -> AsyncSession:
        return self._async_session_factory()


# ── Bot Repository ────────────────────────────────────────────────────


class SqlAlchemyBotRepository:
    def __init__(self, store: SqlAlchemyStore):
        self._store = store

    async def create(
        self,
        name: str,
        personality: str,
        first_message: str,
        scenario: str = "",
        description: str = "",
        avatar_path: str | None = None,
        categories: list[str] | None = None,
        bot_type: BotType = BotType.RP,
        alternate_greetings: list[str] | None = None,
        mes_example: str = "",
        dynamic_system_prompt: str = "",
        world_state_prompt: str = "",
    ) -> int:
        categories_json = json.dumps(categories or [])
        alternate_greetings_json = json.dumps(alternate_greetings or [])
        async with self._store._async_session_factory() as session:
            bot = Bot(
                name=name,
                personality=personality,
                first_message=first_message,
                scenario=scenario,
                description=description,
                avatar_path=avatar_path,
                categories=categories_json,
                bot_type=bot_type,
                alternate_greetings=alternate_greetings_json,
                mes_example=mes_example,
                dynamic_system_prompt=dynamic_system_prompt,
                world_state_prompt=world_state_prompt,
            )
            session.add(bot)
            await session.commit()
            await session.refresh(bot)
            return bot.id

    async def update(
        self,
        bot_id: int,
        name: str,
        personality: str,
        first_message: str,
        scenario: str = "",
        description: str = "",
        avatar_path: str | None = None,
        categories: list[str] | None = None,
        bot_type: BotType = BotType.RP,
        alternate_greetings: list[str] | None = None,
        mes_example: str | None = None,
        dynamic_system_prompt: str | None = None,
        world_state_prompt: str | None = None,
    ) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(Bot).where(Bot.id == bot_id))
            bot = result.scalar_one_or_none()
            if bot is None:
                raise NotFoundError(f"Bot {bot_id} was not found")
            bot.name = name
            bot.personality = personality
            bot.first_message = first_message
            bot.scenario = scenario
            bot.description = description
            bot.avatar_path = avatar_path
            bot.categories = json.dumps(categories or [])
            bot.bot_type = bot_type.value if hasattr(bot_type, "value") else bot_type
            bot.alternate_greetings = json.dumps(alternate_greetings or [])
            bot.mes_example = mes_example or ""
            if mes_example is not None:
                bot.mes_example = mes_example
            if dynamic_system_prompt is not None:
                bot.dynamic_system_prompt = dynamic_system_prompt
            if world_state_prompt is not None:
                bot.world_state_prompt = world_state_prompt
            session.add(bot)
            await session.commit()

    async def get(self, bot_id: int) -> Bot | None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(Bot).where(Bot.id == bot_id))
            return result.scalar_one_or_none()

    async def list(self) -> list[Bot]:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(Bot).order_by(Bot.id))
            return list(result.scalars().all())

    async def delete(self, bot_id: int) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(Bot).where(Bot.id == bot_id))
            bot = result.scalar_one_or_none()
            if bot is not None:
                await session.delete(bot)
                await session.commit()

    async def get_with_thread_counts(self) -> list[tuple[Bot, int]]:
        """Return bots paired with their thread count."""
        async with self._store._async_session_factory() as session:
            counts_result = await session.execute(
                select(ChatThread.bot_id, func.count(ChatThread.id)).group_by(ChatThread.bot_id)
            )
            counts = dict(counts_result.all())
            bots_result = await session.execute(select(Bot).order_by(Bot.id))
            bots = list(bots_result.scalars().all())
            return [(bot, counts.get(bot.id, 0)) for bot in bots]


# ── Thread Repository ────────────────────────────────────────────────


class SqlAlchemyThreadRepository:
    def __init__(self, store: SqlAlchemyStore):
        self._store = store

    async def create(
        self, bot_id: int, name: str = "Новая беседа", persona_id: int | None = None
    ) -> int:
        async with self._store._async_session_factory() as session:
            thread = ChatThread(bot_id=bot_id, name=name, persona_id=persona_id)
            session.add(thread)
            await session.commit()
            await session.refresh(thread)
            return thread.id

    async def get(self, thread_id: int) -> ThreadDTO | None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ChatThread).where(ChatThread.id == thread_id))
            thread = result.scalar_one_or_none()
            if thread is None:
                return None
            return ThreadDTO(
                id=thread.id,
                bot_id=thread.bot_id,
                name=thread.name,
                summary=thread.summary,
                persona_id=thread.persona_id,
                created_at=thread.created_at,
                parent_thread_id=thread.parent_thread_id,
            )

    async def list_for_bot(self, bot_id: int) -> list[ThreadDTO]:
        async with self._store._async_session_factory() as session:
            rows_result = await session.execute(
                text("""
                    SELECT
                        t.id,
                        t.bot_id,
                        t.name,
                        t.summary,
                        t.persona_id,
                        p.name AS persona_name,
                        t.created_at,
                        t.parent_thread_id
                    FROM chat_threads t
                    LEFT JOIN user_personas p ON t.persona_id = p.id
                    WHERE t.bot_id = :bot_id
                    ORDER BY t.created_at ASC, t.id ASC
                """),
                {"bot_id": bot_id},
            )
            rows = rows_result.fetchall()
            return [
                ThreadDTO(
                    id=row.id,
                    bot_id=row.bot_id,
                    name=row.name,
                    summary=row.summary,
                    persona_id=row.persona_id,
                    persona_name=row.persona_name,
                    created_at=row.created_at,
                    parent_thread_id=row.parent_thread_id,
                )
                for row in rows
            ]

    async def rename(self, thread_id: int, name: str) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ChatThread).where(ChatThread.id == thread_id))
            thread = result.scalar_one_or_none()
            if thread is None:
                raise NotFoundError(f"Thread {thread_id} was not found")
            thread.name = name
            session.add(thread)
            await session.commit()

    async def update_summary(self, thread_id: int, summary: str) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ChatThread).where(ChatThread.id == thread_id))
            thread = result.scalar_one_or_none()
            if thread is not None:
                thread.summary = summary
                session.add(thread)
                await session.commit()

    async def delete(self, thread_id: int) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ChatThread).where(ChatThread.id == thread_id))
            thread = result.scalar_one_or_none()
            if thread is not None:
                await session.delete(thread)
                await session.commit()

    async def set_persona(self, thread_id: int, persona_id: int | None) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ChatThread).where(ChatThread.id == thread_id))
            thread = result.scalar_one_or_none()
            if thread is None:
                raise NotFoundError(f"Thread {thread_id} was not found")
            thread.persona_id = persona_id
            session.add(thread)
            await session.commit()

    async def find_by_bot_and_persona(
        self, bot_id: int, persona_id: int | None
    ) -> ThreadDTO | None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(ChatThread)
                .where(ChatThread.bot_id == bot_id)
                .where(ChatThread.persona_id == persona_id)
                .order_by(ChatThread.created_at.desc())
                .limit(1)
            )
            thread = result.scalar_one_or_none()
            if thread is None:
                return None
            return ThreadDTO(
                id=thread.id,
                bot_id=thread.bot_id,
                name=thread.name,
                summary=thread.summary,
                persona_id=thread.persona_id,
                created_at=thread.created_at,
                parent_thread_id=thread.parent_thread_id,
            )

    async def set_pending_greeting(self, thread_id: int, content: str) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ChatThread).where(ChatThread.id == thread_id))
            thread = result.scalar_one_or_none()
            if thread is None:
                raise NotFoundError(f"Thread {thread_id} was not found")
            thread.pending_greeting = content
            session.add(thread)
            await session.commit()

    async def list_recent(
        self, limit: int = 20, bot_id: int | None = None
    ) -> list[RecentThreadDTO]:
        async with self._store._async_session_factory() as session:
            bot_filter = "AND t.bot_id = :bid" if bot_id else ""
            params: dict = {"lim": limit}
            if bot_id:
                params["bid"] = bot_id

            rows_result = await session.execute(
                text(f"""
                    SELECT
                        t.id AS thread_id,
                        t.bot_id,
                        t.summary,
                        b.name AS bot_name,
                        b.avatar_path AS bot_avatar_path,
                        b.categories AS bot_categories,
                        b.personality AS bot_personality,
                        p.name AS persona_name,
                        p.avatar_path AS persona_avatar_path,
                        COALESCE(last.content, '') AS last_message_preview,
                        COALESCE(last.last_at, t.created_at) AS last_message_at
                    FROM chat_threads t
                    JOIN bots b ON t.bot_id = b.id
                    LEFT JOIN user_personas p ON t.persona_id = p.id
                    LEFT JOIN (
                        SELECT c1.thread_id, c1.content, c1.timestamp AS last_at
                        FROM conversations c1
                        INNER JOIN (
                            SELECT thread_id, MAX(id) AS max_id
                            FROM conversations
                            GROUP BY thread_id
                        ) c2 ON c1.id = c2.max_id
                    ) last ON last.thread_id = t.id
                    WHERE 1=1 {bot_filter}
                    ORDER BY last_message_at DESC
                    LIMIT :lim
                """),
                params,
            )
            rows = rows_result.fetchall()

            result = []
            for row in rows:
                cats: list[str] = []
                try:
                    parsed = json.loads(row.bot_categories or "[]")
                    cats = parsed if isinstance(parsed, list) else []
                except (json.JSONDecodeError, TypeError):
                    pass

                result.append(
                    RecentThreadDTO(
                        thread_id=row.thread_id,
                        bot_id=row.bot_id,
                        summary=row.summary,
                        bot_name=row.bot_name,
                        bot_avatar_path=row.bot_avatar_path,
                        bot_categories=cats,
                        bot_personality=row.bot_personality or "",
                        persona_name=row.persona_name,
                        persona_avatar_path=row.persona_avatar_path,
                        last_message_preview=(row.last_message_preview or "")[:150],
                        last_message_at=row.last_message_at,
                    )
                )
            return result


# ── Message Repository ────────────────────────────────────────────────


class SqlAlchemyMessageRepository:
    def __init__(self, store: SqlAlchemyStore):
        self._store = store

    async def save(
        self,
        thread_id: int,
        role: str,
        content: str,
        branch_group: str | None = None,
        branch_index: int = 0,
        is_active: bool = True,
        short_content: str | None = None,
        timestamp: datetime | None = None,
        generation_status: str = "complete",
        reasoning: str | None = None,
        dynamic_system_prompt: str | None = None,
        # ``None`` (default) leaves ``state`` as NULL on insert —
        # preserves historical behaviour where state was unset on
        # user messages and pre-state-update assistant rows. ``""``
        # explicitly stores an empty string. The combination is what
        # lets ``ThreadService.update_message`` faithfully copy the
        # original message's state into a new branch without losing
        # the difference between "no snapshot yet" (NULL) and
        # "snapshot was empty" (empty string).
        state: str | None = None,
    ) -> int | None:
        if not content:
            return None
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ChatThread).where(ChatThread.id == thread_id))
            if result.scalar_one_or_none() is None:
                raise NotFoundError(f"Thread {thread_id} was not found")
            msg = Conversation(
                thread_id=thread_id,
                role=role,
                content=content,
                reasoning=reasoning,
                dynamic_system_prompt=dynamic_system_prompt,
                short_content=short_content,
                branch_group=branch_group,
                branch_index=branch_index,
                is_active=is_active,
                generation_status=generation_status,
                # SQLAlchemy treats ``None`` as "leave the column at
                # its default (NULL)"; empty strings are persisted
                # as empty strings. The aggregate list_for_thread
                # projection reads them identically so the DTO
                # contract holds either way.
                state=state,
            )
            if timestamp is not None:
                msg.timestamp = timestamp
            session.add(msg)
            await session.commit()
            await session.refresh(msg)
            return msg.id

    async def save_branch(
        self,
        thread_id: int,
        role: str,
        content: str,
        branch_group: str,
        branch_index: int,
        timestamp: datetime | None = None,
        generation_status: str = "complete",
        reasoning: str | None = None,
        state: str | None = None,
        dynamic_system_prompt: str | None = None,
    ) -> int | None:
        return await self.save(
            thread_id,
            role,
            content,
            branch_group=branch_group,
            branch_index=branch_index,
            is_active=True,
            timestamp=timestamp,
            generation_status=generation_status,
            reasoning=reasoning,
            state=state,
            dynamic_system_prompt=dynamic_system_prompt,
        )

    async def save_exchange(
        self,
        thread_id: int,
        user_input: str,
        assistant_response: str,
        reasoning: str | None = None,
    ) -> None:
        if not user_input and not assistant_response:
            return
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ChatThread).where(ChatThread.id == thread_id))
            if result.scalar_one_or_none() is None:
                raise NotFoundError(f"Thread {thread_id} was not found")
            to_add = []
            if user_input:
                to_add.append(Conversation(thread_id=thread_id, role="user", content=user_input))
            if assistant_response:
                to_add.append(
                    Conversation(
                        thread_id=thread_id,
                        role="assistant",
                        content=assistant_response,
                        reasoning=reasoning,
                    )
                )
            if to_add:
                session.add_all(to_add)
                await session.commit()

    async def list_for_thread(
        self,
        thread_id: int,
        limit: int = 20,
        before_id: int | None = None,
    ) -> list[MessageDTO]:
        async with self._store._async_session_factory() as session:
            # Build the active-message filter. ``before_id`` is an
            # exclusive keyset cursor — when provided, we return only
            # messages with a strictly smaller id (older ones), which
            # is what the chat UI needs to lazily load history in pages
            # of `limit` from newest to oldest.
            conditions = [
                Conversation.thread_id == thread_id,
                (Conversation.branch_group.is_(None)) | (Conversation.is_active),
            ]
            if before_id is not None:
                conditions.append(Conversation.id < before_id)
            # 1. Get active messages (no branch_group, or is_active)
            messages_result = await session.execute(
                select(Conversation)
                .where(*conditions)
                .order_by(Conversation.timestamp.desc(), Conversation.id.desc())
                .limit(limit)
            )
            messages = list(messages_result.scalars().all())

            # 2. Collect branch_group IDs from active messages that have them
            branch_group_list = [m.branch_group for m in messages if m.branch_group is not None]

            # 3. Fetch all versions for those branch groups via raw SQL (more reliable)
            versions_by_group: dict[str, list[MessageDTO]] = {}
            if branch_group_list:
                placeholders = ",".join([":bg" + str(i) for i in range(len(branch_group_list))])
                params = {
                    **{f"bg{i}": g for i, g in enumerate(branch_group_list)},
                    "tid": thread_id,
                }
                rows_result = await session.execute(
                    text(
                        f"SELECT id, thread_id, role, content, short_content, timestamp, "
                        f"branch_group, branch_index, is_active, dynamic_system_prompt "
                        f"FROM conversations "
                        f"WHERE thread_id = :tid AND branch_group IN ({placeholders}) "
                        f"ORDER BY branch_index ASC"
                    ),
                    params,
                )
                rows = rows_result.fetchall()

                for row in rows:
                    bg = str(row.branch_group) if row.branch_group else None
                    if bg is None:
                        continue
                    if bg not in versions_by_group:
                        versions_by_group[bg] = []
                    versions_by_group[bg].append(
                        MessageDTO(
                            id=row.id,
                            role=row.role,
                            content=row.content,
                            short_content=row.short_content,
                            created_at=None,  # raw SQL returns string, skip tz conversion
                            branch_group=bg,
                            branch_index=row.branch_index or 0,
                            is_active=bool(row.is_active),
                            # Added in 0.0.6: read the floating-prompt
                            # column through the raw-SQL branch path
                            # too. Without this, regenerated branches
                            # saved via ``save_branch`` lose the
                            # snapshot on read because the SELECT
                            # clause above never asked for the
                            # column and ``MessageDTO`` defaults to
                            # ``None`` on construction.
                            dynamic_system_prompt=row.dynamic_system_prompt or None,
                        )
                    )

            # 4. Build result with versions attached
            # NOTE: ``msg.state`` and ``msg.dynamic_system_prompt`` are
            # propagated into the DTO so the frontend can render
            # the world-state panel and the floating-prompt panel.
            # The 0.0.4 migration added ``state`` to ``Conversation``;
            # the f1e2d3c4b5a6 migration added
            # ``dynamic_system_prompt``. Without propagating them,
            # the DTO is forever ``None`` regardless of what the
            # background state-update task writes — the original 0.0.4
            # code omitted the fields and tests didn't catch it
            # because they round-tripped through the in-memory fake
            # repo, which built the DTO directly.
            result: list[MessageDTO] = []
            for msg in reversed(messages):
                if not msg.content:
                    continue
                dto = MessageDTO(
                    id=msg.id,
                    role=msg.role,
                    content=msg.content,
                    short_content=msg.short_content,
                    reasoning=msg.reasoning,
                    state=msg.state,
                    dynamic_system_prompt=msg.dynamic_system_prompt or None,
                    created_at=_ensure_tz(msg.timestamp),
                    branch_group=msg.branch_group,
                    branch_index=msg.branch_index,
                    is_active=msg.is_active,
                )
                if msg.branch_group and msg.branch_group in versions_by_group:
                    dto.versions = versions_by_group[msg.branch_group]
                result.append(dto)
            return result

    async def clear_thread(self, thread_id: int) -> None:
        async with self._store._async_session_factory() as session:
            await session.execute(
                sa_delete(Conversation).where(Conversation.thread_id == thread_id)
            )
            await session.commit()

    async def list_active_until(
        self,
        thread_id: int,
        until_message_id: int,
    ) -> list[MessageDTO]:
        """Return active messages whose id <= ``until_message_id``, oldest first.

        Implements the contract documented on
        ``MessageRepository.list_active_until`` — same active-chain
        filter as ``list_for_thread`` (rows with no ``branch_group``
        plus the active row of any branch group). Used by
        ``ThreadService.fork_at_message`` so the SQL filter is
        byte-identical to the one the chat UI sees (pitfall 6at):
        diverging filters here would silently drop messages the user
        is currently looking at.

        We deliberately do NOT call ``list_for_thread`` and trim in
        Python — that path uses ``LIMIT`` and would miss older rows
        once the chain grows past the page size. A targeted SELECT with
        ``id <= until_message_id`` is both cheaper and correctness-
        critical.

        Returns an empty list for an unknown thread / an id that
        doesn't belong to the thread; the service layer decides
        whether that's an error.
        """
        async with self._store._async_session_factory() as session:
            rows_result = await session.execute(
                select(Conversation)
                .where(
                    Conversation.thread_id == thread_id,
                    Conversation.id <= until_message_id,
                    # Same filter as ``list_for_thread`` — keep these
                    # two clauses in lockstep when the schema evolves.
                    (Conversation.branch_group.is_(None)) | (Conversation.is_active.is_(True)),
                )
                .order_by(Conversation.id.asc())
            )
            rows = list(rows_result.scalars().all())
            return [
                MessageDTO(
                    id=row.id,
                    role=cast("Literal['system', 'user', 'assistant']", row.role),
                    content=row.content,
                    short_content=row.short_content,
                    reasoning=row.reasoning,
                    state=row.state,
                    # ``dynamic_system_prompt`` is NOT NULL with
                    # server_default='' — coerce the empty-string
                    # default to ``None`` so the DTO matches what
                    # ``list_for_thread`` emits (panel renders only
                    # when a real value is present).
                    dynamic_system_prompt=row.dynamic_system_prompt or None,
                    created_at=_ensure_tz(row.timestamp),
                    branch_group=None,
                    branch_index=0,
                    is_active=True,
                    # Generation status is preserved per-row because
                    # the fork snapshots the conversation as-is,
                    # including any partial / streaming artefacts.
                    generation_status=row.generation_status,
                )
                for row in rows
                if row.content
            ]

    async def count_active(self, thread_id: int) -> int:
        """Count the active chain of messages in ``thread_id``.

        Mirrors ``list_for_thread``'s branch-group filter: rows with
        no ``branch_group`` plus the active row of any branch group.
        Used by ``ThreadService.get_stats`` so the chat header reports
        total messages rather than the latest paginated window.

        Returns 0 for unknown / empty threads (no error — distinguishes
        "missing" from "empty" via the route layer).
        """
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(func.count(Conversation.id)).where(
                    Conversation.thread_id == thread_id,
                    (Conversation.branch_group.is_(None)) | (Conversation.is_active.is_(True)),
                    Conversation.content.isnot(None) & (Conversation.content != ""),
                )
            )
            return int(result.scalar() or 0)

    async def update(self, message_id: int, content: str) -> None:
        if not content:
            return
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == message_id)
            )
            msg = result.scalar_one_or_none()
            if msg is None:
                raise NotFoundError(f"Message {message_id} was not found")
            msg.content = content
            session.add(msg)
            await session.commit()

    async def update_state(self, message_id: int, state: str) -> None:
        """Persist the bot's world-state snapshot for an assistant message.

        Used by the background state-update task after each chat turn.
        The state value is opaque (YAML, JSON, prose — whatever the
        bot's ``world_state_prompt`` asks the LLM for). We do NOT
        parse, validate, or constrain it.
        """
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == message_id)
            )
            msg = result.scalar_one_or_none()
            if msg is None:
                raise NotFoundError(f"Message {message_id} was not found")
            msg.state = state
            session.add(msg)
            await session.commit()

    async def get_previous_assistant_state(
        self, thread_id: int, before_message_id: int | None = None
    ) -> str:
        """Return the most recent non-empty ``state`` for an assistant
        message in this thread, optionally restricted to messages with
        id strictly less than ``before_message_id``.

        Returns ``""`` when no such state exists.

        Implementation notes:

        1. A single targeted query (``WHERE role='assistant'
           AND state IS NOT NULL AND state != '' ORDER BY id DESC LIMIT 1``)
           is far cheaper and safer than ``list_for_thread(limit=2)`` —
           the latter returns the two newest rows in DESC, which can both
           be user messages if the conversation just had two consecutive
           user turns (e.g. an edit that landed as a fresh insert), and
           the caller would silently fall through to ``previous_state=""``
           even though a perfectly valid state exists further back.

        2. **Active-branch filter.** We must constrain the lookup to
           messages on the *active* branch — the state-update
           regenerator feeds the LLM the previous turn's snapshot so
           it can carry world state across the conversation. A
           regenerate / retry creates a new ``branch_group`` and
           deactivates the old one (``is_active=False``); without
           this filter, ``get_previous_assistant_state`` would happily
           hand back a state from the stale inactive branch and the
           regenerator would hallucinate a world-state carryover that
           doesn't match what's actually on screen. Same applies to
           messages with no ``branch_group`` — those are the
           pre-branching legacy rows and they're always considered
           active (they're the trunk).
        """
        async with self._store._async_session_factory() as session:
            conditions = [
                Conversation.thread_id == thread_id,
                Conversation.role == "assistant",
                Conversation.state.isnot(None),
                Conversation.state != "",
                # Branch-aware filter. ``branch_group IS NULL`` means
                # the message predates branching and is always
                # considered part of the active chain; otherwise
                # only ``is_active=True`` rows count. The mirror
                # condition lives in ``list_for_thread`` so the chat
                # UI and the LLM see the same world.
                (Conversation.branch_group.is_(None)) | (Conversation.is_active.is_(True)),
            ]
            if before_message_id is not None:
                conditions.append(Conversation.id < before_message_id)
            result = await session.execute(
                select(Conversation.state)
                .where(*conditions)
                .order_by(Conversation.id.desc())
                .limit(1)
            )
            value = result.scalar_one_or_none()
            return value or ""

    async def delete(self, message_id: int) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == message_id)
            )
            msg = result.scalar_one_or_none()
            if msg is not None:
                await session.delete(msg)
                await session.commit()

    async def delete_from(self, thread_id: int, message_id: int) -> None:
        """Delete message_id and all messages after it in the thread."""
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == message_id)
            )
            target = result.scalar_one_or_none()
            if target is None:
                raise NotFoundError(f"Message {message_id} was not found")
            await session.execute(
                sa_delete(Conversation).where(
                    Conversation.thread_id == thread_id,
                    Conversation.id >= message_id,
                )
            )
            await session.commit()

    async def delete_after(self, thread_id: int, message_id: int) -> None:
        """Delete all messages AFTER message_id (exclusive) in a thread."""
        async with self._store._async_session_factory() as session:
            await session.execute(
                sa_delete(Conversation).where(
                    Conversation.thread_id == thread_id,
                    Conversation.id > message_id,
                )
            )
            await session.commit()

    async def get_versions(self, message_id: int) -> list[MessageDTO]:
        """Get all messages in the same branch group."""
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == message_id)
            )
            msg = result.scalar_one_or_none()
            if msg is None or msg.branch_group is None:
                return []
            versions_result = await session.execute(
                select(Conversation)
                .where(
                    Conversation.branch_group == msg.branch_group,
                    Conversation.thread_id == msg.thread_id,
                )
                .order_by(Conversation.branch_index.asc())
            )
            versions = list(versions_result.scalars().all())
            return [
                MessageDTO(
                    id=v.id,
                    role=v.role,
                    content=v.content,
                    short_content=v.short_content,
                    reasoning=v.reasoning,
                    # 0.0.6 fix: ``get_versions`` built the DTO without
                    # carrying over ``dynamic_system_prompt`` — the
                    # column was saved by ``save_branch`` but the
                    # read path silently dropped it, so the chat UI
                    # never showed the floating-prompt panel for
                    # regenerated branches. Mirror ``list_for_thread``
                    # and propagate the column here too.
                    dynamic_system_prompt=v.dynamic_system_prompt or None,
                    created_at=v.timestamp,
                    branch_group=v.branch_group,
                    branch_index=v.branch_index,
                    is_active=v.is_active,
                )
                for v in versions
            ]  # fmt: skip

    async def switch_version(self, branch_group: str, target_version_id: int) -> None:
        """Set target_version_id is_active=True, all others in branch_group=False."""
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == target_version_id)
            )
            target = result.scalar_one_or_none()
            if target is None:
                raise NotFoundError(f"Message {target_version_id} was not found")
            await session.execute(
                sa_update(Conversation)
                .where(
                    Conversation.branch_group == branch_group,
                    Conversation.thread_id == target.thread_id,
                )
                .values(is_active=False)
            )
            target.is_active = True
            session.add(target)
            await session.commit()

    async def get_last_bot_message(self, thread_id: int) -> MessageDTO | None:
        """Get the last assistant message in a thread ordered by id."""
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .where(
                    Conversation.thread_id == thread_id,
                    Conversation.role == "assistant",
                )
                .order_by(Conversation.id.desc())
                .limit(1)
            )
            msg = result.scalar_one_or_none()
            if msg is None:
                return None
            return MessageDTO(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                short_content=msg.short_content,
                created_at=msg.timestamp,
                branch_group=msg.branch_group,
                branch_index=msg.branch_index,
                is_active=msg.is_active,
            )

    async def get_first_assistant(self, thread_id: int) -> MessageDTO | None:
        """Get the chronologically-first assistant message in a thread (by id ASC)."""
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation)
                .where(
                    Conversation.thread_id == thread_id,
                    Conversation.role == "assistant",
                )
                .order_by(Conversation.id.asc())
                .limit(1)
            )
            msg = result.scalar_one_or_none()
            if msg is None:
                return None
            return MessageDTO(
                id=msg.id,
                role=msg.role,
                content=msg.content,
                short_content=msg.short_content,
                created_at=msg.timestamp,
                branch_group=msg.branch_group,
                branch_index=msg.branch_index,
                is_active=msg.is_active,
            )

    async def update_content(self, message_id: int, content: str) -> None:
        """Overwrite a message's content."""
        if not content:
            return
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == message_id)
            )
            msg = result.scalar_one_or_none()
            if msg is None:
                raise NotFoundError(f"Message {message_id} was not found")
            msg.content = content
            session.add(msg)
            await session.commit()

    async def save_first_assistant_if_absent(self, thread_id: int, content: str) -> bool:
        """Atomically insert bot.first_message iff no assistant row exists.

        Race-safety (RC1.2 in docs/review.md): under two concurrent
        ``stream_message`` calls on a fresh thread, both would otherwise
        pass the ``SELECT 1`` existence check, both would try to
        ``INSERT``, and one would either crash on a uniqueness
        constraint or duplicate the row. We side-step that with a
        single session that does ``SELECT COUNT + INSERT`` and rely
        on SQLite's single-writer serialization (aiosqlite blocks
        concurrent writers at the connection level) to keep the
        check-then-act window tight.

        Returns True iff a row was actually inserted. False means the
        thread already had an assistant message (or the thread id
        doesn't exist — both outcomes are no-ops from the caller's
        point of view).
        """
        from sqlalchemy import func
        from sqlalchemy import select as sa_select

        if not content:
            return False
        async with self._store._async_session_factory() as session:
            # 1. Confirm the thread exists (raises NotFoundError otherwise,
            #    matching the contract of ``save``).
            thread_result = await session.execute(
                sa_select(ChatThread).where(ChatThread.id == thread_id)
            )
            if thread_result.scalar_one_or_none() is None:
                raise NotFoundError(f"Thread {thread_id} was not found")
            # 2. Already have an assistant message? Bail out.
            count_result = await session.execute(
                sa_select(func.count(Conversation.id))
                .where(Conversation.thread_id == thread_id)
                .where(Conversation.role == "assistant")
            )
            existing = count_result.scalar_one()
            if existing > 0:
                return False
            # 3. Insert. Two writers can race past step 2 because aiosqlite
            #    serializes them, but the second one will see ``existing > 0``
            #    on the next attempt and bail.
            session.add(
                Conversation(
                    thread_id=thread_id,
                    role="assistant",
                    content=content,
                    generation_status="complete",
                )
            )
            await session.commit()
            return True

    async def update_short_content(self, message_id: int, short_content: str) -> None:
        """Update the short_content field of a message — first writer wins.

        Idempotency contract (RC5 in docs/review.md): if a concurrent
        summarizer has already set ``short_content`` for this message, this
        call becomes a no-op. This is safer than "last-writer-wins" because:

        * Two parallel ``summarize_message`` calls for the same ``message_id``
          (e.g. ``batch_summarize`` + an on-save hook) both produce
          semantically-valid summaries; the first to commit is good enough
          and the second one would only churn the row.
        * The summarizer is best-effort — losing the second write doesn't
          cause a worse user experience than losing the first.

        Implementation: ``UPDATE ... SET short_content=:v WHERE id=:id
        AND short_content IS NULL`` — if the WHERE clause matches 0 rows,
        the message either doesn't exist or was already summarized; both
        outcomes are silent no-ops. UPDATE on 0 rows is not an error in
        SQL, so we always commit and let the DB no-op.
        """
        from sqlalchemy import update as sa_update

        async with self._store._async_session_factory() as session:
            await session.execute(
                sa_update(Conversation)
                .where(
                    Conversation.id == message_id,
                    Conversation.short_content.is_(None),
                )
                .values(short_content=short_content)
            )
            await session.commit()

    async def update_branch(
        self,
        message_id: int,
        branch_group: str,
        branch_index: int,
        is_active: bool,
    ) -> None:
        """Update branch fields on an existing message."""
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(Conversation).where(Conversation.id == message_id)
            )
            msg = result.scalar_one_or_none()
            if msg is not None:
                msg.branch_group = branch_group
                msg.branch_index = branch_index
                msg.is_active = is_active
                session.add(msg)
                await session.commit()

    async def deactivate_branch_group(self, branch_group: str, thread_id: int) -> None:
        """Set is_active=False for all messages in a branch group within a thread."""
        async with self._store._async_session_factory() as session:
            await session.execute(
                sa_update(Conversation)
                .where(
                    Conversation.branch_group == branch_group,
                    Conversation.thread_id == thread_id,
                )
                .values(is_active=False)
            )
            await session.commit()


# ── Persona Repository ────────────────────────────────────────────────


class SqlAlchemyPersonaRepository:
    def __init__(self, store: SqlAlchemyStore):
        self._store = store

    async def create(self, name: str, description: str = "", avatar_path: str | None = None) -> int:
        async with self._store._async_session_factory() as session:
            p = UserPersona(name=name, description=description, avatar_path=avatar_path)
            session.add(p)
            await session.commit()
            await session.refresh(p)
            return p.id

    async def update(
        self,
        persona_id: int,
        name: str,
        description: str = "",
        avatar_path: str | None = None,
    ) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(UserPersona).where(UserPersona.id == persona_id))
            p = result.scalar_one_or_none()
            if p is None:
                raise NotFoundError(f"Persona {persona_id} was not found")
            p.name = name
            p.description = description
            p.avatar_path = avatar_path
            p.updated_at = p.updated_at  # touch
            session.add(p)
            await session.commit()

    async def get(self, persona_id: int) -> UserPersonaDTO | None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(UserPersona).where(UserPersona.id == persona_id))
            p = result.scalar_one_or_none()
            if p is None:
                return None
            return UserPersonaDTO(
                id=p.id,
                name=p.name,
                avatar_path=p.avatar_path,
                description=p.description,
            )

    async def list(self) -> list[UserPersonaDTO]:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(UserPersona).order_by(UserPersona.id))
            personas = list(result.scalars().all())
            return [
                UserPersonaDTO(
                    id=p.id,
                    name=p.name,
                    avatar_path=p.avatar_path,
                    description=p.description,
                )
                for p in personas
            ]

    async def delete(self, persona_id: int) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(UserPersona).where(UserPersona.id == persona_id))
            p = result.scalar_one_or_none()
            if p is not None:
                await session.delete(p)
                await session.commit()


# ── Thread File Repository ────────────────────────────────────────────


class SqlAlchemyThreadFileRepository:
    def __init__(self, store: SqlAlchemyStore):
        self._store = store

    async def save(
        self,
        thread_id: int,
        filename: str,
        file_type: str,
        storage_path: str,
        extracted_text: str | None = None,
    ) -> ThreadFileDTO:
        async with self._store._async_session_factory() as session:
            tf = ThreadFile(
                thread_id=thread_id,
                filename=filename,
                file_type=file_type,
                storage_path=storage_path,
                extracted_text=extracted_text,
            )
            session.add(tf)
            await session.commit()
            await session.refresh(tf)
            return ThreadFileDTO(
                id=tf.id,
                thread_id=tf.thread_id,
                message_id=tf.message_id,
                filename=tf.filename,
                file_type=tf.file_type,
                storage_path=tf.storage_path,
                extracted_text=tf.extracted_text,
                created_at=tf.created_at,
            )

    async def list_for_thread(self, thread_id: int) -> list[ThreadFileDTO]:
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(ThreadFile)
                .where(ThreadFile.thread_id == thread_id)
                .order_by(ThreadFile.created_at.asc())
            )
            files = list(result.scalars().all())
            return [
                ThreadFileDTO(
                    id=f.id,
                    thread_id=f.thread_id,
                    message_id=f.message_id,
                    filename=f.filename,
                    file_type=f.file_type,
                    storage_path=f.storage_path,
                    extracted_text=f.extracted_text,
                    created_at=f.created_at,
                )
                for f in files
            ]

    async def get(self, file_id: int) -> ThreadFileDTO | None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ThreadFile).where(ThreadFile.id == file_id))
            tf = result.scalar_one_or_none()
            if tf is None:
                return None
            return ThreadFileDTO(
                id=tf.id,
                thread_id=tf.thread_id,
                message_id=tf.message_id,
                filename=tf.filename,
                file_type=tf.file_type,
                storage_path=tf.storage_path,
                extracted_text=tf.extracted_text,
                created_at=tf.created_at,
            )

    async def delete(self, file_id: int) -> None:
        import os

        async with self._store._async_session_factory() as session:
            result = await session.execute(select(ThreadFile).where(ThreadFile.id == file_id))
            tf = result.scalar_one_or_none()
            if tf is None:
                return
            # Remove file from disk
            try:
                os.remove(tf.storage_path)
            except OSError:
                pass
            await session.delete(tf)
            await session.commit()

    async def delete_by_thread(self, thread_id: int) -> None:
        import os
        import shutil

        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(ThreadFile).where(ThreadFile.thread_id == thread_id)
            )
            files = list(result.scalars().all())
            # Remove upload directory for this thread
            if files:
                upload_dir = os.path.dirname(files[0].storage_path)
                try:
                    shutil.rmtree(upload_dir, ignore_errors=True)
                except OSError:
                    pass
            for tf in files:
                await session.delete(tf)
            await session.commit()

    async def attach_to_message(self, file_ids: list[int], message_id: int) -> None:
        async with self._store._async_session_factory() as session:
            await session.execute(
                sa_update(ThreadFile)
                .where(ThreadFile.id.in_(file_ids))
                .values(message_id=message_id)
            )
            await session.commit()

    async def list_for_message(self, message_id: int) -> list[ThreadFileDTO]:
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(ThreadFile)
                .where(ThreadFile.message_id == message_id)
                .order_by(ThreadFile.created_at.asc())
            )
            files = list(result.scalars().all())
            return [
                ThreadFileDTO(
                    id=f.id,
                    thread_id=f.thread_id,
                    message_id=f.message_id,
                    filename=f.filename,
                    file_type=f.file_type,
                    storage_path=f.storage_path,
                    extracted_text=f.extracted_text,
                    created_at=f.created_at,
                )
                for f in files
            ]


# ── Backward-compatible facade ────────────────────────────────────────


def _make_sync_url(db_path: str) -> str:
    """Convert an async SQLite URL to a sync one for ConversationManager."""
    if db_path.startswith("sqlite+aiosqlite:///"):
        return "sqlite:///" + db_path[len("sqlite+aiosqlite:///") :]
    if db_path.startswith("sqlite:///"):
        return db_path
    return f"sqlite:///{db_path}"


# ── Bot Version Repository ───────────────────────────────────────────


class SqlAlchemyBotVersionRepository:
    """Async SQLite/aiosqlite-backed repository for ``BotVersion``.

    Versions are append-only snapshots: list queries return newest first
    (DESC by ``version_number``) so the UI can render the timeline
    without a sort pass. ``get_max_version`` returns 0 for a bot with no
    versions, so the service can compute ``next = max + 1`` without a
    separate empty-check.
    """

    def __init__(self, store: SqlAlchemyStore):
        self._store = store

    async def add(self, version: BotVersion) -> int:
        async with self._store._async_session_factory() as session:
            session.add(version)
            await session.commit()
            await session.refresh(version)
            return version.id

    async def list_by_bot(self, bot_id: int) -> list[BotVersion]:
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(BotVersion)
                .where(BotVersion.bot_id == bot_id)
                .order_by(BotVersion.version_number.desc())
            )
            return list(result.scalars().all())

    async def get(self, version_id: int) -> BotVersion | None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(BotVersion).where(BotVersion.id == version_id))
            return result.scalar_one_or_none()

    async def get_max_version(self, bot_id: int) -> int:
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(func.max(BotVersion.version_number)).where(BotVersion.bot_id == bot_id)
            )
            value = result.scalar()
            return int(value) if value is not None else 0

    async def delete(self, version_id: int) -> None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(select(BotVersion).where(BotVersion.id == version_id))
            version = result.scalar_one_or_none()
            if version is not None:
                await session.delete(version)
                await session.commit()


def _parse_categories(categories: str | list | None) -> list[str]:
    """Parse the categories field — may be JSON string, list, or None."""
    if isinstance(categories, list):
        return categories
    if not categories:
        return []
    import json

    try:
        parsed = json.loads(categories)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


# ── Settings Repository ────────────────────────────────────────────


class SqlAlchemySettingsRepository:
    """Persists the singleton ``app_settings`` row.

    Honors the ``id=1`` invariant from the schema by:

    * Reading with ``WHERE id=1`` so a stray second row is invisible.
    * Upserting the same id — INSERT, on IntegrityError UPDATE — so
      two callers racing on first write don't end up with two rows.
    """

    _ROW_ID = 1

    def __init__(self, store: SqlAlchemyStore):
        self._store = store

    async def get_bot_categories(self) -> list[str] | None:
        async with self._store._async_session_factory() as session:
            result = await session.execute(
                select(AppSettings).where(AppSettings.id == self._ROW_ID)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _parse_categories(row.bot_categories_json)

    async def set_bot_categories(self, categories: list[str], payload: str) -> None:
        """Upsert the singleton row with the encoded JSON ``payload``.

        ``categories`` is passed alongside for repositories that
        prefer to encode internally; this implementation uses the
        pre-built JSON bytes the service already produced so the
        on-disk format is decided in exactly one place.
        """
        del categories  # payload is the source of truth
        async with self._store._async_session_factory() as session:
            # Try INSERT; if the singleton already exists, UPDATE.
            # SQLite throws IntegrityError on PK conflict — turn
            # that into the upsert path so two concurrent first
            # writes don't end up with two rows.
            try:
                session.add(
                    AppSettings(
                        id=self._ROW_ID,
                        bot_categories_json=payload,
                    )
                )
                await session.commit()
            except Exception:
                await session.rollback()
                await session.execute(
                    sa_update(AppSettings)
                    .where(AppSettings.id == self._ROW_ID)
                    .values(bot_categories_json=payload)
                )
                await session.commit()
