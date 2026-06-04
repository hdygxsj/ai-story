from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceNodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    node_type: str = Field(min_length=1, max_length=40)
    parent_id: UUID | None = None


class WorkspaceNodeUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    parent_id: UUID | None = None
    position: int | None = Field(default=None, ge=0)


class WorkspaceNodeReorderItem(BaseModel):
    id: UUID
    parent_id: UUID | None = None
    position: int = Field(ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    status: str | None = Field(default=None, min_length=1, max_length=40)


class WorkspaceNodeReorderRequest(BaseModel):
    items: list[WorkspaceNodeReorderItem] = Field(min_length=1)


class WorkspaceNodeResponse(BaseModel):
    id: UUID
    novel_id: UUID
    parent_id: UUID | None
    document_id: UUID | None
    title: str
    node_type: str
    status: str
    position: int

    model_config = ConfigDict(from_attributes=True)
