from typing import Any, TypedDict
from uuid import UUID


class AgentState(TypedDict, total=False):
    novel_id: UUID
    document_id: UUID | None
    message: str
    selected_text: str | None
    response: str
    context_status: list[str]
    proposed_payload: dict[str, Any] | None
