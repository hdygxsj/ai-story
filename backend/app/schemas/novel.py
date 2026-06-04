from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str = ""


class NovelImport(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    format: str = Field(default="markdown", pattern="^(markdown|txt)$")
    description: str = ""


class NovelUpdate(BaseModel):
    default_model_profile_id: UUID | None = None


class NovelResponse(BaseModel):
    id: UUID
    title: str
    description: str
    default_model_profile_id: UUID | None

    model_config = ConfigDict(from_attributes=True)
