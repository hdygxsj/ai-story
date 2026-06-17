from typing import Any

from pydantic import BaseModel, Field


class AgentToolInfo(BaseModel):
    name: str
    description: str
    args_schema: dict[str, Any]


class AgentToolRunRequest(BaseModel):
    arguments: dict[str, Any] = Field(default_factory=dict)
    document_id: str | None = None


class AgentToolRunResponse(BaseModel):
    tool_name: str
    result: Any
