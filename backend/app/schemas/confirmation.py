from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ConfirmationResponse(BaseModel):
    id: UUID
    action_type: str
    status: str
    payload: dict[str, Any]
    document_id: UUID | None = None
    is_stale: bool = False
    before_text: str | None = None
    after_text: str | None = None

    model_config = ConfigDict(from_attributes=True)
