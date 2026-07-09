"""add dynamic_system_prompt to conversations

Revision ID: f1e2d3c4b5a6
Revises: e5f6a7b8c9d0
Create Date: 2026-07-09 14:00:00.000000

Closes the loop on the dev-mode debug panel: the 0.0.4 migration
added ``bots.dynamic_system_prompt`` and ``conversations.state`` but
forgot the matching ``conversations.dynamic_system_prompt`` column.

The application code (see ``SqlAlchemyMessageRepository.save``)
already accepts ``dynamic_system_prompt`` as a per-save parameter
and the chat orchestrator passes it on every assistant message
that was streamed with a non-empty floating prompt. Without this
column the value lands on the in-memory ``Conversation`` instance
but is silently dropped by INSERT — the field is forever ``None``
when the frontend re-fetches the message via ``listMessages``.

The fix: add the column to ``conversations``, propagate it through
the repo's INSERT and SELECT paths (see the matching change in
``list_for_thread``).

Like the surrounding 0.0.4 fields this is additive and defaults
to ``""`` (empty string) so older rows read back cleanly.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1e2d3c4b5a6"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "conversations",
        sa.Column(
            "dynamic_system_prompt",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversations", "dynamic_system_prompt")
