from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceNodeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    node_type: str = Field(min_length=1, max_length=40)
    parent_id: UUID | None = None


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
