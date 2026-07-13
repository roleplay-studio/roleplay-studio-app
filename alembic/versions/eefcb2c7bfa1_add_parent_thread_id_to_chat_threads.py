"""add parent_thread_id to chat_threads

Adds a nullable self-referencing FK so the UI can render the
fork lineage as a tree (commit 848d26c created the fork but did
not persist the parent link). ON DELETE SET NULL preserves
forks independently of their source.

SQLite cannot ALTER TABLE ADD CONSTRAINT directly, so we use
batch mode (copy-and-move strategy). This is the project's
established pattern for any post-baseline FK addition.

Revision ID: eefcb2c7bfa1
Revises: f1e2d3c4b5a6
Create Date: 2026-07-13
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "eefcb2c7bfa1"
down_revision: str | None = "f1e2d3c4b5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add the column first (no constraint — works in plain ALTER).
    op.add_column(
        "chat_threads",
        sa.Column("parent_thread_id", sa.Integer(), nullable=True),
    )
    # SQLite cannot ALTER TABLE ADD CONSTRAINT, so we use batch
    # mode (copy-and-move) to attach the FK + index together.
    with op.batch_alter_table("chat_threads", recreate="always") as batch_op:
        batch_op.create_foreign_key(
            "fk_chat_threads_parent_thread_id",
            "chat_threads",
            ["parent_thread_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_chat_threads_parent_thread_id",
            ["parent_thread_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("chat_threads", recreate="always") as batch_op:
        batch_op.drop_index("ix_chat_threads_parent_thread_id")
        batch_op.drop_constraint(
            "fk_chat_threads_parent_thread_id", type_="foreignkey"
        )
    op.drop_column("chat_threads", "parent_thread_id")
