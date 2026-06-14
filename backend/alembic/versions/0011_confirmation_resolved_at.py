"""Add resolved_at to pending confirmations.

Revision ID: 0011_confirmation_resolved_at
Revises: 0010_material_changes
Create Date: 2026-06-14 15:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_confirmation_resolved_at"
down_revision: str | None = "0010_material_changes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "pending_confirmations",
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pending_confirmations", "resolved_at")
