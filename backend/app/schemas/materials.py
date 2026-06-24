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
    position: int | None = Field(default=None, ge=1, description="Explicit display order; lower comes first")
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


class CharacterAttributeCreate(BaseModel):
    character_name: str = Field(min_length=1, max_length=200)
    attribute_key: str = Field(min_length=1, max_length=120)
    value: Any
    unit: str = Field(default="", max_length=60)
    scope: str = Field(default="current", min_length=1, max_length=120)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CharacterAttributeUpdate(BaseModel):
    character_name: str | None = Field(default=None, min_length=1, max_length=200)
    attribute_key: str | None = Field(default=None, min_length=1, max_length=120)
    value: Any | None = None
    unit: str | None = Field(default=None, max_length=60)
    scope: str | None = Field(default=None, min_length=1, max_length=120)
    metadata: dict[str, Any] | None = None


class CharacterAttributeResponse(CharacterAttributeCreate):
    id: UUID
    novel_id: UUID
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")

    model_config = ConfigDict(from_attributes=True)


class InventoryItemCreate(BaseModel):
    owner_name: str = Field(min_length=1, max_length=200)
    item_name: str = Field(min_length=1, max_length=200)
    quantity: float
    unit: str = Field(default="", max_length=60)
    location_name: str | None = Field(default=None, max_length=200)
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class InventoryItemUpdate(BaseModel):
    owner_name: str | None = Field(default=None, min_length=1, max_length=200)
    item_name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: float | None = None
    unit: str | None = Field(default=None, max_length=60)
    location_name: str | None = Field(default=None, max_length=200)
    description: str | None = None
    metadata: dict[str, Any] | None = None


class InventoryItemResponse(InventoryItemCreate):
    id: UUID
    novel_id: UUID
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")

    model_config = ConfigDict(from_attributes=True)


class MapLocationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    location_type: str = Field(default="location", min_length=1, max_length=80)
    summary: str = Field(min_length=1)
    parent_name: str | None = Field(default=None, max_length=200)
    coordinates: dict[str, Any] = Field(default_factory=dict)
    adjacent_location_names: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MapLocationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    location_type: str | None = Field(default=None, min_length=1, max_length=80)
    summary: str | None = Field(default=None, min_length=1)
    parent_name: str | None = Field(default=None, max_length=200)
    coordinates: dict[str, Any] | None = None
    adjacent_location_names: list[str] | None = None
    metadata: dict[str, Any] | None = None


class MapLocationResponse(MapLocationCreate):
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
    position: int | None = Field(default=None, ge=1, description="Explicit display order; lower comes first")
    metadata: dict[str, Any] | None = None


class TimelineEventReorder(BaseModel):
    event_ids: list[UUID] = Field(min_length=1, description="Timeline event ids in desired display order")


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
