import asyncio
import time
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import MemorySaver

from app.agent.graph import build_agent_graph
from app.agent.runtime import _checkpoint_safe_state, graph_invoke_config
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

    assert first["configurable"]["thread_id"] == second["configurable"]["thread_id"]
    assert first["configurable"]["thread_id"] == f"conversation:v2:{conversation_id}"


def test_checkpoint_state_serializes_uuid_values() -> None:
    novel_id = uuid4()
    document_id = uuid4()
    state = _checkpoint_safe_state(
        {
            "novel_id": novel_id,
            "document_id": document_id,
            "message": "hello",
            "nested": {"ids": [novel_id]},
            "model_profile": object(),
        }
    )

    assert state["novel_id"] == str(novel_id)
    assert state["document_id"] == str(document_id)
    assert state["nested"] == {"ids": [str(novel_id)]}
    assert "model_profile" not in state


@pytest.mark.asyncio
async def test_checkpoint_preserves_tool_results_across_turns_and_appends_current_message(monkeypatch) -> None:
    seen_messages: list[list[object]] = []

    @tool
    def lookup_lighthouse() -> dict[str, str]:
        """Look up lighthouse facts."""
        return {"fact": "灯塔资料：守灯人把钥匙藏在镜片下。"}

    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            seen_messages.append(list(messages))
            human_messages = [message for message in messages if isinstance(message, HumanMessage)]
            tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
            if tool_messages and human_messages[-1].content == "检索灯塔资料":
                return AIMessage(content="已查到灯塔资料。")
            if human_messages[-1].content == "检索灯塔资料":
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "lookup_lighthouse",
                            "args": {},
                            "id": "call_lookup_lighthouse",
                        }
                    ],
                )
            assert any("守灯人把钥匙藏在镜片下" in str(message.content) for message in tool_messages)
            assert human_messages[-1].content == "刚才查到什么？"
            return AIMessage(content="刚才查到钥匙藏在镜片下。")

    class FakeProfile:
        context_window = 128000

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())

    conversation_id = uuid4()
    graph = build_agent_graph(tools=[lookup_lighthouse], checkpointer=MemorySaver(), model_profile=FakeProfile())

    first = await graph.ainvoke(
        {
            "message": "检索灯塔资料",
            "system_prompt": "第一轮系统上下文",
        },
        graph_invoke_config(conversation_id),
    )
    assert first["response"] == "已查到灯塔资料。"

    second = await graph.ainvoke(
        {
            "message": "刚才查到什么？",
            "system_prompt": "第二轮系统上下文",
        },
        graph_invoke_config(conversation_id),
    )

    assert second["response"] == "刚才查到钥匙藏在镜片下。"
    assert len(seen_messages) >= 3
    second_turn_messages = seen_messages[-1]
    assert isinstance(second_turn_messages[0], SystemMessage)
    assert str(second_turn_messages[0].content).startswith("第二轮系统上下文")
    assert any(isinstance(message, ToolMessage) for message in second_turn_messages)
    assert [message.content for message in second_turn_messages if isinstance(message, HumanMessage)][-1] == "刚才查到什么？"


@pytest.mark.asyncio
async def test_async_agent_node_does_not_block_event_loop_for_sync_models(monkeypatch) -> None:
    class BlockingChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            time.sleep(0.2)
            return AIMessage(content="同步模型完成。")

    class FakeProfile:
        context_window = 128000

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": BlockingChatModel())

    graph = build_agent_graph(checkpointer=MemorySaver(), model_profile=FakeProfile())
    task = asyncio.create_task(graph.ainvoke({"message": "测试同步模型"}, graph_invoke_config(uuid4())))

    await asyncio.sleep(0.05)

    assert not task.done()
    result = await task
    assert result["response"] == "同步模型完成。"
