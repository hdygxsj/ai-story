from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ModelProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_kind: str = Field(min_length=1, max_length=50)
    base_url: str | None = Field(default=None, max_length=2048)
    api_key: str = Field(min_length=1, max_length=4096)
    chat_provider_kind: str | None = Field(default=None, max_length=50)
    chat_model: str = Field(min_length=1, max_length=255)
    chat_base_url: str | None = Field(default=None, max_length=2048)
    chat_api_key: str | None = Field(default=None, max_length=4096)
    writing_provider_kind: str | None = Field(default=None, max_length=50)
    writing_model: str = Field(min_length=1, max_length=255)
    writing_base_url: str | None = Field(default=None, max_length=2048)
    writing_api_key: str | None = Field(default=None, max_length=4096)
    summary_provider_kind: str | None = Field(default=None, max_length=50)
    summary_model: str = Field(min_length=1, max_length=255)
    summary_base_url: str | None = Field(default=None, max_length=2048)
    summary_api_key: str | None = Field(default=None, max_length=4096)
    embedding_provider_kind: str | None = Field(default=None, max_length=50)
    embedding_model: str = Field(min_length=1, max_length=255)
    embedding_base_url: str | None = Field(default=None, max_length=2048)
    embedding_api_key: str | None = Field(default=None, max_length=4096)
    supports_tool_calling: bool = True
    supports_json_mode: bool = True
    supports_streaming: bool = True
    context_window: int = Field(default=128000, gt=0)
    embedding_dimensions: int = Field(default=1536, gt=0)
    extra_headers: dict[str, Any] = Field(default_factory=dict)


class ModelProfileResponse(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    provider_kind: str
    base_url: str | None
    chat_provider_kind: str | None
    chat_model: str
    chat_base_url: str | None
    writing_provider_kind: str | None
    writing_model: str
    writing_base_url: str | None
    summary_provider_kind: str | None
    summary_model: str
    summary_base_url: str | None
    embedding_provider_kind: str | None
    embedding_model: str
    embedding_base_url: str | None
    supports_tool_calling: bool
    supports_json_mode: bool
    supports_streaming: bool
    context_window: int
    embedding_dimensions: int
    extra_headers: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
