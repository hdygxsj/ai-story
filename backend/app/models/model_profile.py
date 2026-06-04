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
    chat_provider_kind: Mapped[str | None] = mapped_column(String(50))
    chat_model: Mapped[str] = mapped_column(String(255), nullable=False)
    chat_base_url: Mapped[str | None] = mapped_column(String(2048))
    chat_api_key_ciphertext: Mapped[str | None] = mapped_column(String(4096))
    writing_provider_kind: Mapped[str | None] = mapped_column(String(50))
    writing_model: Mapped[str] = mapped_column(String(255), nullable=False)
    writing_base_url: Mapped[str | None] = mapped_column(String(2048))
    writing_api_key_ciphertext: Mapped[str | None] = mapped_column(String(4096))
    summary_provider_kind: Mapped[str | None] = mapped_column(String(50))
    summary_model: Mapped[str] = mapped_column(String(255), nullable=False)
    summary_base_url: Mapped[str | None] = mapped_column(String(2048))
    summary_api_key_ciphertext: Mapped[str | None] = mapped_column(String(4096))
    embedding_provider_kind: Mapped[str | None] = mapped_column(String(50))
    embedding_model: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding_base_url: Mapped[str | None] = mapped_column(String(2048))
    embedding_api_key_ciphertext: Mapped[str | None] = mapped_column(String(4096))
    supports_tool_calling: Mapped[bool] = mapped_column(default=True, nullable=False)
    supports_json_mode: Mapped[bool] = mapped_column(default=True, nullable=False)
    supports_streaming: Mapped[bool] = mapped_column(default=True, nullable=False)
    context_window: Mapped[int] = mapped_column(Integer, default=128000, nullable=False)
    embedding_dimensions: Mapped[int] = mapped_column(Integer, default=1536, nullable=False)
    extra_headers: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    owner = relationship("User")
