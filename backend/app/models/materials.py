from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CreativeAsset(Base):
    __tablename__ = "creative_assets"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    asset_type: Mapped[str] = mapped_column(String(60), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    event_time: Mapped[str] = mapped_column(String(120), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class CharacterState(Base):
    __tablename__ = "character_states"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    character_name: Mapped[str] = mapped_column(String(200), nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str] = mapped_column(String(120), nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


class RelationshipEdge(Base):
    __tablename__ = "relationship_edges"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    novel_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("novels.id", ondelete="CASCADE"), index=True)
    source_character: Mapped[str] = mapped_column(String(200), nullable=False)
    target_character: Mapped[str] = mapped_column(String(200), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[dict[str, Any]] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
