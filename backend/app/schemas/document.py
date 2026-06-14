from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentUpdate(BaseModel):
    content: dict[str, Any]


class DocumentResponse(BaseModel):
    id: UUID
    novel_id: UUID
    content: dict[str, Any]

    model_config = ConfigDict(from_attributes=True)


class DocumentVersionResponse(BaseModel):
    id: UUID
    document_id: UUID
    source: str
    content: dict[str, Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
