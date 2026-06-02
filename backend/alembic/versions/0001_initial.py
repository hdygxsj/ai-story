"""Initial schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-03 01:17:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "model_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("provider_kind", sa.String(length=50), nullable=False),
        sa.Column("base_url", sa.String(length=2048), nullable=True),
        sa.Column("api_key_ciphertext", sa.String(length=4096), nullable=False),
        sa.Column("chat_model", sa.String(length=255), nullable=False),
        sa.Column("writing_model", sa.String(length=255), nullable=False),
        sa.Column("summary_model", sa.String(length=255), nullable=False),
        sa.Column("embedding_model", sa.String(length=255), nullable=False),
        sa.Column("supports_tool_calling", sa.Boolean(), nullable=False),
        sa.Column("supports_json_mode", sa.Boolean(), nullable=False),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("embedding_dimensions", sa.Integer(), nullable=True),
        sa.Column("extra_headers", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_model_profiles_owner_id", "model_profiles", ["owner_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_model_profiles_owner_id", table_name="model_profiles")
    op.drop_table("model_profiles")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
