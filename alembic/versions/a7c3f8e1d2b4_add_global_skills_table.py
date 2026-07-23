"""add global_skills table and Bot.skill_ids

Spec: docs/superpowers/specs/2026-07-17-skills-design.md §4.1

Introduces the Skills feature (Claude/Anthropic style): a global
library of reusable instructions (GlobalSkill) plus a per-bot
subscription list stored as JSON-encoded list[int] in Bot.skill_ids.

Pattern: same JSON-as-TEXT approach used by ``categories`` and
``alternate_greetings`` — no separate M2M table for the MVP, see
spec §4.1 trade-offs.

Note on UNIQUE constraint: declared inline in the create_table call
(parity with baseline_schema.py) rather than via batch_alter_table.
SQLite + batch_alter_table on a freshly-created table doesn't reliably
preserve the table — recreates it under a temp name which is fine for
ADD COLUMN on existing tables but flaky for create-then-constrain.

Revision ID: a7c3f8e1d2b4
Revises: eefcb2c7bfa1
Create Date: 2026-07-17
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3f8e1d2b4"
down_revision: str | None = "eefcb2c7bfa1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ── New table: global_skills ─────────────────────────────────
    # UNIQUE + index on ``name`` declared inline so SQLite creates them
    # atomically with the table. Idempotent with batch_alter_table
    # isn't reliable on freshly-created tables (see module docstring).
    op.create_table(
        "global_skills",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False, server_default=""),
        sa.Column("instruction", sa.String(), nullable=False),
        sa.Column("tags", sa.String(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.current_timestamp(),
        ),
        sa.UniqueConstraint("name", name="uq_global_skills_name"),
    )
    op.create_index("ix_global_skills_name", "global_skills", ["name"])

    # ── Add Bot.skill_ids ───────────────────────────────────────
    # Stored as JSON-encoded TEXT (parity with categories, see spec
    # §4.1). Nullable=False + server_default='[]' so existing bot
    # rows pick up the empty-list default without manual migration.
    op.add_column(
        "bots",
        sa.Column(
            "skill_ids",
            sa.String(),
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_global_skills_name", table_name="global_skills")
    op.drop_constraint("uq_global_skills_name", "global_skills", type_="unique")
    op.drop_table("global_skills")
    op.drop_column("bots", "skill_ids")
