from typing import Any, TypedDict
from uuid import UUID

from app.models import ModelProfile


class AgentState(TypedDict, total=False):
    novel_id: UUID
    document_id: UUID | None
    message: str
    selected_text: str | None
    messages: list[Any]
    model_profile: ModelProfile | None
    response: str
    context_status: list[str]
    proposed_payload: dict[str, Any] | None
