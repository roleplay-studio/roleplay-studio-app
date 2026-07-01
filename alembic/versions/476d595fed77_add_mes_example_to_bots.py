"""add mes_example to bots

Revision ID: 476d595fed77
Revises: 2a4ae02ae5b1
Create Date: 2026-06-15

Adds a `mes_example` column to the `bots` table to round-trip the
V1/V2/V3 character card `mes_example` field (few-shot dialogue
examples). Default empty string — non-breaking for existing bots.
"""

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "476d595fed77"
down_revision: str | None = "2a4ae02ae5b1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "bots",
        sa.Column(
            "mes_example",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("bots", "mes_example")
