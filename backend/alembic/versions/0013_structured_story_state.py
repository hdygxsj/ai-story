"""Add structured story state tables.

Revision ID: 0013_structured_story_state
Revises: 0012_timeline_event_position
Create Date: 2026-06-24 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_structured_story_state"
down_revision: str | None = "0012_timeline_event_position"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "character_attributes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("character_name", sa.String(length=200), nullable=False),
        sa.Column("attribute_key", sa.String(length=120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("unit", sa.String(length=60), nullable=False),
        sa.Column("scope", sa.String(length=120), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_character_attributes_novel_id", "character_attributes", ["novel_id"])

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("owner_name", sa.String(length=200), nullable=False),
        sa.Column("item_name", sa.String(length=200), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=60), nullable=False),
        sa.Column("location_name", sa.String(length=200), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_inventory_items_novel_id", "inventory_items", ["novel_id"])

    op.create_table(
        "map_locations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("novel_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("location_type", sa.String(length=80), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("parent_name", sa.String(length=200), nullable=True),
        sa.Column("coordinates", sa.JSON(), nullable=False),
        sa.Column("adjacent_location_names", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_map_locations_novel_id", "map_locations", ["novel_id"])


def downgrade() -> None:
    op.drop_index("ix_map_locations_novel_id", table_name="map_locations")
    op.drop_table("map_locations")
    op.drop_index("ix_inventory_items_novel_id", table_name="inventory_items")
    op.drop_table("inventory_items")
    op.drop_index("ix_character_attributes_novel_id", table_name="character_attributes")
    op.drop_table("character_attributes")
