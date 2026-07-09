"""add floating prompts and world state

Revision ID: e5f6a7b8c9d0
Revises: d1e7c4a0f9b2
Create Date: 2026-07-08 15:30:00.000000

Adds three columns that close the loop on "long-chat stability" +
"world state persistence":

* ``bots.dynamic_system_prompt`` — a free-text reminder injected
  right before the last user turn on every chat request. Solves the
  instruction-drift problem (bots stop following their personality
  after 100+ messages).
* ``bots.world_state_prompt`` — the system prompt used only for the
  background job that updates ``conversations.state``. The bot
  developer decides the format (YAML, JSON, prose, anything).
* ``conversations.state`` — opaque per-message snapshot, populated
  by the background job after each assistant response. Nullable on
  older messages that predate this feature.

All three are additive, defaults are non-breaking (``""`` or
``NULL``), and the migration is the down-compatible predecessor
shape used by ``476d595fed77_add_mes_example_to_bots.py``.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d1e7c4a0f9b2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "bots",
        sa.Column(
            "dynamic_system_prompt",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "bots",
        sa.Column(
            "world_state_prompt",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )
    # ``state`` is nullable=True on purpose: existing assistant
    # messages predate this feature and the value genuinely is
    # unknown. A subsequent background regenerator can fill it in
    # lazily if the operator wants to backfill.
    op.add_column(
        "conversations",
        sa.Column(
            "state",
            sa.String(),
            nullable=True,
            server_default=None,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversations", "state")
    op.drop_column("bots", "world_state_prompt")
    op.drop_column("bots", "dynamic_system_prompt")