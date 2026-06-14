from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.checkpoint import get_checkpointer
from app.agent.graph import build_agent_graph
from app.agent.tool_runtime import build_runtime_tools
from app.agent.tool_trace import build_tool_call_record, summarize_tool_result, tool_result_status
from app.models import ModelProfile


def graph_invoke_config(conversation_id: UUID | None) -> dict[str, Any]:
    config: dict[str, Any] = {"recursion_limit": 150}
    if conversation_id is not None:
        config["configurable"] = {"thread_id": f"{conversation_id}:{uuid4()}"}
    return config


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
    tool_calls: list[dict[str, Any]] = []
    tool_calls_by_id: dict[str, dict[str, Any]] = {}

    async for event in graph.astream_events(
        invoke_state,
        graph_invoke_config(conversation_id),
        version="v2",
    ):
        event_type = event.get("event")
        if event_type == "on_chat_model_stream":
            chunk = event.get("data", {}).get("chunk")
            content = getattr(chunk, "content", "")
            if isinstance(content, str) and content:
                yield "delta", content
            additional_kwargs = getattr(chunk, "additional_kwargs", None) or {}
            reasoning = additional_kwargs.get("reasoning_content")
            if isinstance(reasoning, str) and reasoning:
                yield "reasoning", reasoning
            continue

        if event_type == "on_tool_start":
            run_id = str(event.get("run_id") or "")
            tool_name = str(event.get("name") or "tool")
            tool_input = event.get("data", {}).get("input")
            record = build_tool_call_record(
                run_id=run_id,
                tool=tool_name,
                status="running",
                args=tool_input,
            )
            tool_calls_by_id[run_id] = record
            tool_calls.append(record)
            yield "tool_call", record
            continue

        if event_type == "on_tool_end":
            run_id = str(event.get("run_id") or "")
            tool_name = str(event.get("name") or "tool")
            output = event.get("data", {}).get("output")
            record = build_tool_call_record(
                run_id=run_id,
                tool=tool_name,
                status=tool_result_status(output),
                args=event.get("data", {}).get("input"),
                summary=summarize_tool_result(output),
            )
            tool_calls_by_id[run_id] = record
            for index, existing in enumerate(tool_calls):
                if existing.get("id") == run_id:
                    tool_calls[index] = record
                    break
            else:
                tool_calls.append(record)
            yield "tool_call", record
            continue

        if event_type == "on_chain_end" and event.get("name") == "LangGraph":
            output = event.get("data", {}).get("output")
            if isinstance(output, dict):
                final_result = output

    done_payload = dict(final_result or {})
    done_payload["tool_calls"] = list(tool_calls)
    yield "done", done_payload
