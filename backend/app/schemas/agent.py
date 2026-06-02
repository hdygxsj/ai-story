from uuid import UUID

from pydantic import BaseModel

from app.schemas.confirmation import ConfirmationResponse


class AgentMessageRequest(BaseModel):
    message: str
    document_id: UUID | None = None
    selected_text: str | None = None


class AgentMessageResponse(BaseModel):
    message: str
    context_status: list[str]
    confirmation: ConfirmationResponse | None = None
