from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.checkpoint import get_checkpointer
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
    owner_id: UUID | None = None,
    novel_id: UUID | None = None,
    conversation_id: UUID | None = None,
) -> dict[str, Any]:
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
    )
    invoke_state = {key: value for key, value in state.items() if key != "model_profile"}
    return await graph.ainvoke(invoke_state, graph_invoke_config(conversation_id))


async def stream_agent_graph(
    session: AsyncSession,
    *,
    state: dict[str, Any],
    model_profile: ModelProfile | None,
    owner_id: UUID | None = None,
    novel_id: UUID | None = None,
    conversation_id: UUID | None = None,
) -> AsyncIterator[tuple[str, Any]]:
    checkpointer = await get_checkpointer()
    tools = build_runtime_tools(
        session,
        model_profile=model_profile,
        owner_id=owner_id,
        novel_id=novel_id,
    )
    graph = build_agent_graph(tools=tools, checkpointer=checkpointer, model_profile=model_profile)
    invoke_state = {key: value for key, value in state.items() if key != "model_profile"}
    final_result: dict[str, Any] | None = None
    async for event in graph.astream_events(
        invoke_state,
        graph_invoke_config(conversation_id),
        version="v2",
    ):
        if event["event"] == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            content = getattr(chunk, "content", "")
            if isinstance(content, str) and content:
                yield "delta", content
        if event["event"] == "on_chain_end" and event.get("name") == "LangGraph":
            output = event.get("data", {}).get("output")
            if isinstance(output, dict):
                final_result = output
    yield "done", final_result or {}
