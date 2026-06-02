from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PendingConfirmation(Base):
    __tablename__ = "pending_confirmations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("novels.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    action_type: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="pending", nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
