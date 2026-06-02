from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RagChunk(Base):
    __tablename__ = "rag_chunks"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("novels.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    source_id: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
