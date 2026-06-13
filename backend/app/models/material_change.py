from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MaterialChange(Base):
    __tablename__ = "material_changes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    material_type: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    material_id: Mapped[UUID] = mapped_column(Uuid, index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_source: Mapped[str] = mapped_column(String(20), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    before_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
