"""Add RAG chunk metadata.

Revision ID: 0005_rag_chunks
Revises: 0004_confirmations
Create Date: 2026-06-03 02:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_rag_chunks"
down_revision: str | None = "0004_confirmations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rag_chunks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "novel_id",
            sa.Uuid(),
            sa.ForeignKey("novels.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rag_chunks_novel_id", "rag_chunks", ["novel_id"])
    op.create_index("ix_rag_chunks_source_type", "rag_chunks", ["source_type"])
    op.create_index("ix_rag_chunks_source_id", "rag_chunks", ["source_id"])


def downgrade() -> None:
    op.drop_index("ix_rag_chunks_source_id", table_name="rag_chunks")
    op.drop_index("ix_rag_chunks_source_type", table_name="rag_chunks")
    op.drop_index("ix_rag_chunks_novel_id", table_name="rag_chunks")
    op.drop_table("rag_chunks")
