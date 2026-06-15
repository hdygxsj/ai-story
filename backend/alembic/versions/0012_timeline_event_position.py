"""Add explicit position to timeline events.

Revision ID: 0012_timeline_event_position
Revises: 0011_confirmation_resolved_at
Create Date: 2026-06-15 00:50:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_timeline_event_position"
down_revision: str | None = "0011_confirmation_resolved_at"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("timeline_events", sa.Column("position", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("timeline_events", "position")
