"""add app_settings singleton

Revision ID: d1e7c4a0f9b2
Revises: 9c8f2a1b3d4e
Create Date: 2026-07-02 22:00:00.000000

Adds a one-row ``app_settings`` table that stores user-managed,
runtime-only configuration that doesn't fit into ``.env`` (lists of
strings, JSON blobs, future toggles). The first concrete column is
``bot_categories_json`` — the configurable list of bot categories,
which used to be a hardcoded module-level constant.

Schema:

* ``id INTEGER PRIMARY KEY CHECK (id = 1)`` — enforces the singleton
  pattern at the DB level. Inserts with ``id != 1`` always fail.
* ``bot_categories_json TEXT NOT NULL DEFAULT '[]'`` — JSON-encoded
  ``list[str]``. The DB enforces NOT NULL so the row always has a
  parsable value (even if empty).
* ``updated_at DATETIME`` — write-time stamped by ``SettingsService``
  via SQLAlchemy defaults, not by Alembic.

The pre-migration hardcoded ``BOT_CATEGORIES`` (Anime/Game/Fantasy…)
is preserved as the *seed* — ``SettingsService.get_bot_categories``
populates the singleton on first read if it's missing. No data
migration is needed because there is no existing settings data.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d1e7c4a0f9b2"
down_revision: str | None = "9c8f2a1b3d4e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Create the singleton settings table."""
    op.create_table(
        "app_settings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "bot_categories_json",
            sa.Text(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("id = 1", name="ck_app_settings_singleton"),
    )


def downgrade() -> None:
    """Drop the singleton settings table."""
    op.drop_table("app_settings")
