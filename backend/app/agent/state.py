from typing import Annotated, Any, TypedDict
from uuid import UUID

from langgraph.graph.message import add_messages

from app.models import ModelProfile


class AgentState(TypedDict, total=False):
    novel_id: UUID
    document_id: UUID | None
    message: str
    selected_text: str | None
    system_prompt: str | None
    messages: Annotated[list[Any], add_messages]
    model_profile: ModelProfile | None
    response: str
    context_status: list[str]
    proposed_payload: dict[str, Any] | None
    confirmation_id: str | None
    workspace_diff: dict[str, Any] | None
    write_retry_count: int
    workspace_nodes: list[dict[str, Any]] | None
