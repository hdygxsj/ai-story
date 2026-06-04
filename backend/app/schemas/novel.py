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


class NovelResponse(BaseModel):
    id: UUID
    title: str
    description: str

    model_config = ConfigDict(from_attributes=True)
