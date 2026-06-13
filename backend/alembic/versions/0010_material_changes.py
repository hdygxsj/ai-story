"""Add material change history.

Revision ID: 0010_material_changes
Revises: 0009_context_management
Create Date: 2026-06-14 02:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_material_changes"
down_revision: str | None = "0009_context_management"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "material_changes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("novel_id", sa.Uuid(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("material_type", sa.String(length=40), nullable=False),
        sa.Column("material_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("actor_source", sa.String(length=20), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_material_changes_novel_id", "material_changes", ["novel_id"])
    op.create_index("ix_material_changes_material_type", "material_changes", ["material_type"])
    op.create_index("ix_material_changes_material_id", "material_changes", ["material_id"])


def downgrade() -> None:
    op.drop_index("ix_material_changes_material_id", table_name="material_changes")
    op.drop_index("ix_material_changes_material_type", table_name="material_changes")
    op.drop_index("ix_material_changes_novel_id", table_name="material_changes")
    op.drop_table("material_changes")
