from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_kind: str = Field(min_length=1, max_length=50)
    base_url: str | None = Field(default=None, max_length=2048)
    api_key: str = Field(min_length=1, max_length=4096)
    chat_model: str = Field(min_length=1, max_length=255)
    writing_model: str = Field(min_length=1, max_length=255)
    summary_model: str = Field(min_length=1, max_length=255)
    embedding_model: str = Field(min_length=1, max_length=255)
    supports_tool_calling: bool = False
    supports_json_mode: bool = False
    supports_streaming: bool = False
    context_window: int | None = Field(default=None, gt=0)
    embedding_dimensions: int | None = Field(default=None, gt=0)
    extra_headers: dict[str, Any] = Field(default_factory=dict)


class ModelProfileResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    provider_kind: str
    base_url: str | None
    chat_model: str
    writing_model: str
    summary_model: str
    embedding_model: str
    supports_tool_calling: bool
    supports_json_mode: bool
    supports_streaming: bool
    context_window: int | None
    embedding_dimensions: int | None
    extra_headers: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
