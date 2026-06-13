from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.checkpoint import get_checkpointer
from app.agent.context import ContextPack
from app.agent.graph import build_agent_graph
from app.agent.tool_runtime import build_runtime_tools
from app.models import ModelProfile


def graph_invoke_config(conversation_id: UUID | None) -> dict[str, Any]:
    if conversation_id is None:
        return {}
    return {"configurable": {"thread_id": str(conversation_id)}}


async def invoke_agent_graph(
    session: AsyncSession,
    *,
    state: dict[str, Any],
    model_profile: ModelProfile | None,
    owner_id: UUID,
    novel_id: UUID,
    conversation_id: UUID | None = None,
) -> dict[str, Any]:
    graph_state = dict(state)
    context_pack = graph_state.pop("context_pack", None)
    graph_state.pop("model_profile", None)
    if context_pack is not None and not isinstance(context_pack, ContextPack):
        raise TypeError("context_pack must be a ContextPack")
    checkpointer = await get_checkpointer()
    tools = build_runtime_tools(
        session,
        model_profile=model_profile,
        owner_id=owner_id,
        novel_id=novel_id,
    )
    graph = build_agent_graph(
        tools=tools,
        checkpointer=checkpointer,
        model_profile=model_profile,
        context_pack=context_pack,
    )
    return await graph.ainvoke(graph_state, graph_invoke_config(conversation_id))
