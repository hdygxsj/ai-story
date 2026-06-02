from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CreativeAssetCreate(BaseModel):
    asset_type: str = Field(min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


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
