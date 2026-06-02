from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ModelProfile(Base):
    __tablename__ = "model_profiles"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str | None] = mapped_column(String(2048))
    api_key_ciphertext: Mapped[str] = mapped_column(String(4096), nullable=False)
    chat_model: Mapped[str] = mapped_column(String(255), nullable=False)
    writing_model: Mapped[str] = mapped_column(String(255), nullable=False)
    summary_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    supports_tool_calling: Mapped[bool] = mapped_column(default=False, nullable=False)
    supports_json_mode: Mapped[bool] = mapped_column(default=False, nullable=False)
    supports_streaming: Mapped[bool] = mapped_column(default=False, nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer)
    extra_headers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    owner = relationship("User")
