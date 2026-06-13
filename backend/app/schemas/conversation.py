from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class ConversationResponse(BaseModel):
    id: UUID
    novel_id: UUID
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
