from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.tools import BaseTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_runtime import build_runtime_tools
from app.agent.tools import get_agent_tools
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import ModelProfile, User
from app.schemas.agent_tools import AgentToolInfo, AgentToolRunRequest, AgentToolRunResponse
from app.services.novels import get_owned_novel

router = APIRouter(tags=["agent-tools"])


def _tool_info(tool: BaseTool) -> AgentToolInfo:
    schema = tool.args_schema.model_json_schema() if tool.args_schema is not None else {}
    return AgentToolInfo(
        name=tool.name,
        description=tool.description or "",
        args_schema=schema,
    )


def _tool_by_name(tool_name: str, tools: list[BaseTool]) -> BaseTool:
    for tool in tools:
        if tool.name == tool_name:
            return tool
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent tool not found")


async def _get_model_profile(
    session: AsyncSession,
    *,
    profile_id: UUID | None,
    owner_id: UUID,
) -> ModelProfile | None:
    if profile_id is None:
        return None
    return await session.scalar(
        select(ModelProfile).where(ModelProfile.id == profile_id, ModelProfile.owner_id == owner_id)
    )


@router.get("/agent-tools", response_model=list[AgentToolInfo])
async def list_agent_tools(
    current_user: Annotated[User, Depends(get_current_user)],
) -> list[AgentToolInfo]:
    _ = current_user
    return [_tool_info(tool) for tool in get_agent_tools()]


@router.get("/agent-tools/{tool_name}", response_model=AgentToolInfo)
async def get_agent_tool(
    tool_name: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> AgentToolInfo:
    _ = current_user
    return _tool_info(_tool_by_name(tool_name, get_agent_tools()))


@router.post("/novels/{novel_id}/agent/tools/{tool_name}", response_model=AgentToolRunResponse)
async def run_agent_tool(
    novel_id: UUID,
    tool_name: str,
    payload: AgentToolRunRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentToolRunResponse:
    novel = await get_owned_novel(session, current_user, novel_id)
    model_profile = await _get_model_profile(
        session,
        profile_id=novel.default_model_profile_id,
        owner_id=current_user.id,
    )
    tools = build_runtime_tools(
        session,
        model_profile=model_profile,
        owner_id=current_user.id,
        novel_id=novel.id,
        document_id=UUID(payload.document_id) if payload.document_id else None,
    )
    tool = _tool_by_name(tool_name, tools)
    result = await tool.ainvoke(payload.arguments)
    return AgentToolRunResponse(tool_name=tool.name, result=result)
