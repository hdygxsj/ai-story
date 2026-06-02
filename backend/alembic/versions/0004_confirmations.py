"""Add pending confirmations.

Revision ID: 0004_confirmations
Revises: 0003_memory
Create Date: 2026-06-03 01:42:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_confirmations"
down_revision: str | None = "0003_memory"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pending_confirmations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "novel_id",
            sa.Uuid(),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_pending_confirmations_novel_id", "pending_confirmations", ["novel_id"])


def downgrade() -> None:
    op.drop_index("ix_pending_confirmations_novel_id", table_name="pending_confirmations")
    op.drop_table("pending_confirmations")
