"""SQLAlchemy ORM models migrated to SQLModel — one model for ORM + Pydantic.

M8 note: the four ``created_at``/``updated_at``/``timestamp`` fields
are typed ``datetime`` without ``sa_column=Column(DateTime(timezone=True))``.
On the current SQLite deployment SQLAlchemy strips tzinfo on read,
so the read path in ``SqlAlchemyStore`` funnels every datetime
through ``_ensure_tz`` (see ``infrastructure/repositories/sqlalchemy.py``).
The real fix is a column migration tracked in docs/review.md (M8);
this docstring is here so the next person who touches a timestamp
field knows about the SQLite workaround.
"""

from datetime import UTC, datetime

from sqlmodel import Field, Relationship, SQLModel


class Bot(SQLModel, table=True):
    __tablename__ = "bots"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)
    description: str = Field(default="")
    personality: str = Field(nullable=False)
    first_message: str = Field(default="")
    scenario: str = Field(default="")
    avatar_path: str | None = Field(default=None, nullable=True)
    categories: str = Field(default="[]")  # JSON list of category names
    bot_type: str = Field(default="rp")  # stored as string, converted to BotType in API layer
    alternate_greetings: str = Field(default="[]")  # JSON list of strings
    mes_example: str = Field(default="")  # V1/V2/V3 few-shot dialogue examples
    # Floating system reminder injected right before the last user turn
    # on every chat request. Solves instruction drift in long chats.
    # See ``docs/superpowers/plans/2026-07-08-bot-floating-prompts-and-world-state.md``
    # for the architecture.
    dynamic_system_prompt: str = Field(default="")
    # System prompt for the background task that updates
    # ``Conversation.state``. The bot developer owns the output format
    # via this prompt (YAML, JSON, prose, custom — anything).
    world_state_prompt: str = Field(default="")
    # JSON list[int] — IDs of attached GlobalSkill rows. See spec §4.1.
    # Empty = no skills (skills-блок не инжектится). Stored as TEXT
    # (parity with ``categories`` and ``alternate_greetings``). On
    # existing DBs, SQLAlchemy ``create_all`` issues ALTER TABLE ADD
    # COLUMN to migrate transparently.
    skill_ids: str = Field(default="[]", nullable=False)

    threads: list["ChatThread"] = Relationship(
        back_populates="bot", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


class GlobalSkill(SQLModel, table=True):
    """Global library of skills, reusable across bots. See spec §4.1.

    Pattern: one row per skill. Bot.skill_ids is a JSON list[int]
    pointing at row IDs (parity with how ``Bot.categories`` works for
    the category registry). The skill content (``instruction``) is the
    markdown prompt that gets injected into the bot's system message
    via the orchestrator's ``_build_skills_block`` helper.

    Identity:
    - ``name`` is the unique human-readable handle. Operators see it in
      Library cards and in the LLM debug modal. Empty / whitespace
      names are rejected at the service layer.
    - ``description`` is the 1-2 line summary shown in the catalog
      catalog AND embedded in the LLM's ``<Skills>...</Skills>`` block.
      Longer details go into ``instruction``.
    - ``instruction`` is the full markdown — only shown in Library
      preview, not in the per-bot catalog (catalog uses description
      to save prompt tokens).
    - ``tags`` is JSON-encoded list[str] for client-side filtering.
    """

    __tablename__ = "global_skills"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, unique=True, index=True)
    description: str = Field(nullable=False, default="")
    instruction: str = Field(nullable=False)
    tags: str = Field(default="[]", nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BotVersion(SQLModel, table=True):
    __tablename__ = "bot_versions"

    id: int | None = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bots.id", ondelete="CASCADE", nullable=False, index=True)
    version_number: int = Field(nullable=False)  # 1, 2, 3 … per bot, monotonic
    snapshot_json: str = Field(nullable=False)  # JSON dump of all Bot fields
    note: str = Field(default="")  # user-provided description
    source: str = Field(default="manual")  # "manual" | "auto"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ThreadFile(SQLModel, table=True):
    __tablename__ = "thread_files"

    id: int | None = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="chat_threads.id", ondelete="CASCADE", nullable=False)
    message_id: int | None = Field(
        default=None,
        foreign_key="conversations.id",
        ondelete="SET NULL",
        nullable=True,
    )
    filename: str = Field(nullable=False)
    file_type: str = Field(nullable=False)
    storage_path: str = Field(nullable=False)
    extracted_text: str | None = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    thread: "ChatThread" = Relationship(back_populates="files")


class ChatThread(SQLModel, table=True):
    __tablename__ = "chat_threads"

    id: int | None = Field(default=None, primary_key=True)
    bot_id: int = Field(foreign_key="bots.id", ondelete="CASCADE", nullable=False)
    name: str = Field(default="Новая беседа")
    summary: str | None = Field(
        default=None, nullable=True
    )  # общее описание последних событий сюжета
    pending_greeting: str | None = Field(
        default=None, nullable=True
    )  # greeting chosen from alternate_greetings; used by the next first-message save
    persona_id: int | None = Field(
        default=None, foreign_key="user_personas.id", ondelete="SET NULL", nullable=True
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    # Fork lineage. NULL = root thread. ON DELETE SET NULL so deleting
    # a source thread doesn't cascade-delete its forks (forks survive
    # independently — see the read-only-source guarantee in the fork
    # spec, commit 848d26c).
    parent_thread_id: int | None = Field(
        default=None,
        foreign_key="chat_threads.id",
        nullable=True,
        index=True,
    )

    bot: Bot = Relationship(back_populates="threads")
    conversations: list["Conversation"] = Relationship(
        back_populates="thread", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )
    files: list["ThreadFile"] = Relationship(
        back_populates="thread",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Conversation(SQLModel, table=True):
    __tablename__ = "conversations"

    id: int | None = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="chat_threads.id", ondelete="CASCADE", nullable=False)
    role: str = Field(nullable=False)
    content: str = Field(nullable=False)
    # Chain-of-thought / reasoning content from reasoning-capable LLMs
    # (DeepSeek, QwQ, o1-style, ...). Kept separate from the visible
    # ``content`` so the frontend can render it in a collapsible panel
    # without re-parsing. ``None`` for messages where the model didn't
    # emit reasoning (most providers, all non-reasoning models).
    reasoning: str | None = Field(default=None, nullable=True)
    # Per-message world-state snapshot (opaque string — bot author
    # chooses the format via ``Bot.world_state_prompt``). Populated
    # by the background state-update task after each assistant
    # response; ``None`` for older messages that predate the feature
    # and for messages where the bot has no ``world_state_prompt``.
    state: str | None = Field(default=None, nullable=True)
    # Floating system-prompt snapshot for the turn that produced this
    # message. Captured at stream time so the chat UI can show what
    # was actually sent to the LLM (``[Reminder] ...`` block). The
    # field is set on assistant messages only when the bot has a
    # non-empty ``Bot.dynamic_system_prompt``; empty string = no
    # floating prompt was sent (the panel simply doesn't render).
    # Added in the f1e2d3c4b5a6 migration — the original 0.0.4
    # code passed this through the repo but never persisted it, so
    # the dev-mode panel was always empty.
    dynamic_system_prompt: str = Field(default="", nullable=False)
    short_content: str | None = Field(
        default=None, nullable=True
    )  # краткая суммаризация этого сообщения
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    branch_group: str | None = Field(default=None, nullable=True)
    branch_index: int = Field(default=0)
    is_active: bool = Field(default=True)
    generation_status: str = Field(default="complete", nullable=False)

    thread: ChatThread = Relationship(back_populates="conversations")


class UserPersona(SQLModel, table=True):
    __tablename__ = "user_personas"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)
    avatar_path: str | None = Field(default=None, nullable=True)
    description: str = Field(default="")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AppSettings(SQLModel, table=True):
    """Singleton settings table — at most one row with ``id=1``.

    Holds runtime-only config that doesn't belong in ``.env``: lists,
    JSON blobs, future feature toggles. The CheckConstraint on ``id``
    (enforced in the alembic migration) is the belt; SQLModel
    repositories treat ``id=1`` as the only valid row and use
    ``synchronize_session=False`` upserts as suspenders.

    Today the only stored value is the user-managed bot category
    list. New columns can be added by separate migrations without
    breaking the schema — existing rows just read ``NULL``/default.
    """

    __tablename__ = "app_settings"

    id: int = Field(default=1, primary_key=True)
    # JSON-encoded list[str]. Stored as TEXT to stay SQLite-friendly
    # without pulling in a JSON column type that would block an
    # eventual Postgres migration. ``serializer`` validates parse-ability
    # on read in SettingsService.
    bot_categories_json: str = Field(default="[]", nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
