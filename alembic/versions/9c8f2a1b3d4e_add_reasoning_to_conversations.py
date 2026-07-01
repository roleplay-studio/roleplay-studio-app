"""add reasoning column to conversations

Revision ID: 9c8f2a1b3d4e
Revises: a1b2c3d4e5f6
Create Date: 2026-06-17 14:00:00.000000

Adds a nullable ``reasoning`` TEXT column to ``conversations`` so the
chain-of-thought emitted by reasoning-capable LLMs (DeepSeek, QwQ,
o1-style) is persisted alongside the visible ``content`` and survives
a page reload.

Nullable + no default so existing rows remain unchanged (no backfill
needed — older messages simply have ``reasoning IS NULL`` and the
frontend hides the panel when the field is missing/empty).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9c8f2a1b3d4e"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("reasoning", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "reasoning")
