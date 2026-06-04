"""Add per-model providers to model profiles."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_model_profile_providers"
down_revision: str | None = "0007_model_profile_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("model_profiles", sa.Column("chat_provider_kind", sa.String(length=50), nullable=True))
    op.add_column("model_profiles", sa.Column("writing_provider_kind", sa.String(length=50), nullable=True))
    op.add_column("model_profiles", sa.Column("summary_provider_kind", sa.String(length=50), nullable=True))
    op.add_column("model_profiles", sa.Column("embedding_provider_kind", sa.String(length=50), nullable=True))


def downgrade() -> None:
    op.drop_column("model_profiles", "embedding_provider_kind")
    op.drop_column("model_profiles", "summary_provider_kind")
    op.drop_column("model_profiles", "writing_provider_kind")
    op.drop_column("model_profiles", "chat_provider_kind")
