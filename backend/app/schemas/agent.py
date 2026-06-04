from uuid import UUID

from typing import Any

from pydantic import BaseModel

from app.schemas.confirmation import ConfirmationResponse
from app.schemas.workspace import WorkspaceNodeResponse


class AgentMessageRequest(BaseModel):
    message: str
    document_id: UUID | None = None
    selected_text: str | None = None


class AgentMessageResponse(BaseModel):
    message: str
    context_status: list[str]
    confirmation: ConfirmationResponse | None = None
    workspace_diff: dict[str, Any] | None = None
    workspace_nodes: list[WorkspaceNodeResponse] | None = None
