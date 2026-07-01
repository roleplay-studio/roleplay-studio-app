"""add generation_status to conversations

Revision ID: 2a4ae02ae5b1
Revises: c2e06d1365f2
Create Date: 2026-06-03 22:22:13.414620

"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "2a4ae02ae5b1"
down_revision: str | None = "c2e06d1365f2"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "conversations",
        sa.Column(
            "generation_status",
            sa.String(),
            nullable=False,
            server_default="complete",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("conversations", "generation_status")
