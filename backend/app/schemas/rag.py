from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RagChunkResponse(BaseModel):
    id: UUID
    source_type: str
    source_id: str
    text: str
    metadata: dict[str, Any] = Field(validation_alias="extra_metadata")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
