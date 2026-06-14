from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_agent_graph
from app.agent.runtime import graph_invoke_config
from app.agent.tool_runtime import build_runtime_tools


@pytest.mark.asyncio
async def test_checkpoint_persists_graph_messages(session) -> None:
    document_id = uuid4()
    novel_id = uuid4()
    tools = build_runtime_tools(session, model_profile=None)
    graph = build_agent_graph(tools=tools, checkpointer=MemorySaver())
    config = {"configurable": {"thread_id": "checkpoint-thread-1"}}

    result = await graph.ainvoke(
        {
            "novel_id": novel_id,
            "document_id": document_id,
            "message": "Rewrite with more tension.",
            "selected_text": "The clinic was quiet.",
        },
        config,
    )

    assert result["proposed_payload"] is not None
    snapshot = await graph.aget_state(config)
    assert snapshot.values.get("messages")
    assert len(snapshot.values["messages"]) >= 2


def test_each_agent_request_gets_an_isolated_checkpoint_thread() -> None:
    conversation_id = uuid4()

    first = graph_invoke_config(conversation_id)
    second = graph_invoke_config(conversation_id)

    assert first["configurable"]["thread_id"] != second["configurable"]["thread_id"]
    assert str(conversation_id) in first["configurable"]["thread_id"]
    assert str(conversation_id) in second["configurable"]["thread_id"]
