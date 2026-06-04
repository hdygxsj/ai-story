"""Add per-model credentials to model profiles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_model_profile_credentials"
down_revision: str | None = "0006_materials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_profiles", sa.Column("chat_base_url", sa.String(length=2048), nullable=True))
    op.add_column("model_profiles", sa.Column("chat_api_key_ciphertext", sa.String(length=4096), nullable=True))
    op.add_column("model_profiles", sa.Column("writing_base_url", sa.String(length=2048), nullable=True))
    op.add_column("model_profiles", sa.Column("writing_api_key_ciphertext", sa.String(length=4096), nullable=True))
    op.add_column("model_profiles", sa.Column("summary_base_url", sa.String(length=2048), nullable=True))
    op.add_column("model_profiles", sa.Column("summary_api_key_ciphertext", sa.String(length=4096), nullable=True))
    op.add_column("model_profiles", sa.Column("embedding_base_url", sa.String(length=2048), nullable=True))
    op.add_column("model_profiles", sa.Column("embedding_api_key_ciphertext", sa.String(length=4096), nullable=True))


def downgrade() -> None:
    op.drop_column("model_profiles", "embedding_api_key_ciphertext")
    op.drop_column("model_profiles", "embedding_base_url")
    op.drop_column("model_profiles", "summary_api_key_ciphertext")
    op.drop_column("model_profiles", "summary_base_url")
    op.drop_column("model_profiles", "writing_api_key_ciphertext")
    op.drop_column("model_profiles", "writing_base_url")
    op.drop_column("model_profiles", "chat_api_key_ciphertext")
    op.drop_column("model_profiles", "chat_base_url")
