"""Add structured creative materials.

Revision ID: 0006_materials
Revises: 0005_rag_chunks
Create Date: 2026-06-03 02:20:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_materials"
down_revision: str | None = "0005_rag_chunks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _material_table(name: str, *columns: sa.Column) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("novel_id", sa.Uuid(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        *columns,
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(f"ix_{name}_novel_id", name, ["novel_id"])


def upgrade() -> None:
    _material_table(
        "creative_assets",
        sa.Column("asset_type", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
    )
    op.create_index("ix_creative_assets_asset_type", "creative_assets", ["asset_type"])
    _material_table(
        "timeline_events",
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("event_time", sa.String(length=120), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
    )
    _material_table(
        "character_states",
        sa.Column("character_name", sa.String(length=200), nullable=False),
        sa.Column("state", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
    )
    _material_table(
        "relationship_edges",
        sa.Column("source_character", sa.String(length=200), nullable=False),
        sa.Column("target_character", sa.String(length=200), nullable=False),
        sa.Column("relationship_type", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_index("ix_relationship_edges_novel_id", table_name="relationship_edges")
    op.drop_table("relationship_edges")
    op.drop_index("ix_character_states_novel_id", table_name="character_states")
    op.drop_table("character_states")
    op.drop_index("ix_timeline_events_novel_id", table_name="timeline_events")
    op.drop_table("timeline_events")
    op.drop_index("ix_creative_assets_asset_type", table_name="creative_assets")
    op.drop_index("ix_creative_assets_novel_id", table_name="creative_assets")
    op.drop_table("creative_assets")
