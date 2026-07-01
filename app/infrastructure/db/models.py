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

    threads: list["ChatThread"] = Relationship(
        back_populates="bot", sa_relationship_kwargs={"cascade": "all, delete-orphan"}
    )


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
