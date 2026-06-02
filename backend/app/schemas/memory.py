from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryReviewCreate(BaseModel):
    memory_type: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    importance: int = 50
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryReviewResponse(BaseModel):
    id: UUID
    memory_type: str
    title: str
    body: str
    importance: int
    status: str

    model_config = ConfigDict(from_attributes=True)


class MemoryItemResponse(BaseModel):
    id: UUID
    memory_type: str
    title: str
    body: str
    importance: int

    model_config = ConfigDict(from_attributes=True)
