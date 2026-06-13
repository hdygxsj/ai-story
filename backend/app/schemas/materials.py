from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreativeAssetCreate(BaseModel):
    asset_type: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreativeAssetUpdate(BaseModel):
    asset_type: str | None = Field(default=None, min_length=1, max_length=60)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] | None = None


class CreativeAssetResponse(CreativeAssetCreate):
    id: UUID
    novel_id: UUID
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")

    model_config = ConfigDict(from_attributes=True)


class TimelineEventCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    event_time: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TimelineEventResponse(TimelineEventCreate):
    id: UUID
    novel_id: UUID
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")

    model_config = ConfigDict(from_attributes=True)


class CharacterStateCreate(BaseModel):
    character_name: str = Field(min_length=1, max_length=200)
    state: str = Field(min_length=1)
    scope: str = Field(default="global", max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterStateResponse(CharacterStateCreate):
    id: UUID
    novel_id: UUID
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")

    model_config = ConfigDict(from_attributes=True)


class RelationshipEdgeCreate(BaseModel):
    source_character: str = Field(min_length=1, max_length=200)
    target_character: str = Field(min_length=1, max_length=200)
    relationship_type: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationshipEdgeResponse(RelationshipEdgeCreate):
    id: UUID
    novel_id: UUID
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")

    model_config = ConfigDict(from_attributes=True)


class TimelineEventUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    event_time: str | None = Field(default=None, min_length=1, max_length=120)
    summary: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] | None = None


class CharacterStateUpdate(BaseModel):
    character_name: str | None = Field(default=None, min_length=1, max_length=200)
    state: str | None = Field(default=None, min_length=1)
    scope: str | None = Field(default=None, min_length=1, max_length=120)
    metadata: dict[str, Any] | None = None


class RelationshipEdgeUpdate(BaseModel):
    source_character: str | None = Field(default=None, min_length=1, max_length=200)
    target_character: str | None = Field(default=None, min_length=1, max_length=200)
    relationship_type: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, min_length=1)
    metadata: dict[str, Any] | None = None


class MaterialChangeResponse(BaseModel):
    id: UUID
    novel_id: UUID
    material_type: str
    material_id: UUID
    action: str
    actor_source: str
    summary: str
    before_data: dict[str, Any] | None = None
    after_data: dict[str, Any] | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
