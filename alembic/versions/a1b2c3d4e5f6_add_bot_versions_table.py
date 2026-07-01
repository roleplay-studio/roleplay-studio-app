"""add bot_versions table

Revision ID: a1b2c3d4e5f6
Revises: 476d595fed77
Create Date: 2026-06-17

Adds a ``bot_versions`` table for the bot-versioning feature.
Each row is a full JSON snapshot of one ``Bot`` at the moment of
capture, plus a user note and a source tag (``manual`` / ``auto``).
``version_number`` is monotonic per ``bot_id``.

Cascading FK on ``bot_id`` ensures versions go away with the bot —
no orphaned history.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "476d595fed77"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "bot_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("bot_id", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot_json", sa.String(), nullable=False),
        sa.Column("note", sa.String(), nullable=False, server_default=""),
        sa.Column("source", sa.String(), nullable=False, server_default="manual"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["bot_id"],
            ["bots.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_bot_versions_bot_id",
        "bot_versions",
        ["bot_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_bot_versions_bot_id", table_name="bot_versions")
    op.drop_table("bot_versions")
