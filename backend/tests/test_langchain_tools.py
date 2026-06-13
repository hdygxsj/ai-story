from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import build_agent_graph, finalize_node
from app.agent.tool_runtime import build_runtime_tools
from app.agent.tools import get_agent_tools
from app.core.crypto import encrypt_api_key
from app.models import MemoryItem, MemoryReviewItem, ModelProfile, Novel, RagChunk, User


def test_agent_tool_registry_exposes_structured_langchain_tools() -> None:
    tools = get_agent_tools()
    tool_names = {tool.name for tool in tools}

    assert all(isinstance(tool, BaseTool) for tool in tools)
    assert all(tool.args_schema is not None for tool in tools)
    assert {
        "read_document",
        "search_memory",
        "search_rag",
        "propose_rewrite",
        "save_key_memory",
        "create_character_asset",
        "create_world_rule",
        "create_timeline_event",
        "update_character_state",
        "propose_workspace_change",
    }.issubset(tool_names)
    assert "propose_key_memory" not in tool_names
    assert "list_memory_review_items" not in tool_names

    save_tool = next(tool for tool in tools if tool.name == "save_key_memory")
    result = save_tool.invoke(
        {
            "novel_id": str(uuid4()),
            "title": "Hidden lineage",
            "body": "Mira is the last heir.",
            "importance": 90,
        }
    )
    assert result["action_type"] == "memory_saved"


@pytest.mark.asyncio
async def test_save_key_memory_uses_current_novel_and_persists_indexed_memory(
    session: AsyncSession,
) -> None:
    user = User(email="tool-memory@example.com", username="tool-memory", password_hash="hash")
    session.add(user)
    await session.flush()
    current_novel = Novel(owner_id=user.id, title="Current Tool Memory")
    requested_novel = Novel(owner_id=user.id, title="Requested Tool Memory")
    session.add_all([current_novel, requested_novel])
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=user.id,
            novel_id=current_novel.id,
        )
    }
    result = await tools["save_key_memory"].ainvoke(
        {
            "novel_id": str(requested_novel.id),
            "title": "Hidden lineage",
            "body": "Mira is the last heir.",
            "importance": 90,
        }
    )

    memories = list(await session.scalars(select(MemoryItem)))
    reviews = list(await session.scalars(select(MemoryReviewItem)))
    chunks = list(await session.scalars(select(RagChunk)))

    assert len(memories) == 1
    memory = memories[0]
    assert memory.novel_id == current_novel.id
    assert memory.memory_type == "key_memory"
    assert memory.title == "Hidden lineage"
    assert memory.body == "Mira is the last heir."
    assert memory.importance == 90
    assert memory.extra_metadata == {"source": "agent_inferred"}
    assert reviews == []

    matching_chunks = [
        chunk
        for chunk in chunks
        if chunk.novel_id == current_novel.id
        and chunk.source_type == "memory"
        and chunk.source_id == str(memory.id)
    ]
    assert len(matching_chunks) == 1
    assert matching_chunks[0].text == "Hidden lineage\nMira is the last heir."
    assert result == {
        "status": "ok",
        "action_type": "memory_saved",
        "message": "已保存关键记忆「Hidden lineage」。",
        "memory_item_id": str(memory.id),
    }


def test_agent_graph_uses_tool_result_for_rewrite_confirmation_payload() -> None:
    document_id = uuid4()
    graph = build_agent_graph()

    result = graph.invoke(
        {
            "novel_id": uuid4(),
            "document_id": document_id,
            "message": "Rewrite this with more tension.",
            "selected_text": "The clinic was quiet.",
        }
    )

    assert result["proposed_payload"]["document_id"] == str(document_id)
    assert result["proposed_payload"]["selected_text"] == "The clinic was quiet."
    assert "replacement_text" in result["proposed_payload"]
    assert result["response"] == "I drafted a tenser replacement. Please confirm before I apply it."


def test_finalize_node_returns_saved_memory_message_without_proposal() -> None:
    result = finalize_node(
        {
            "message": "Remember this.",
            "messages": [
                ToolMessage(
                    content={
                        "status": "ok",
                        "action_type": "memory_saved",
                        "message": "已保存关键记忆「Hidden lineage」。",
                        "memory_item_id": str(uuid4()),
                    },
                    tool_call_id="call_save_key_memory",
                )
            ],
        }
    )

    assert result == {
        "response": "已保存关键记忆「Hidden lineage」。",
        "proposed_payload": None,
    }


def test_agent_chat_uses_configured_model_response(monkeypatch) -> None:
    class FakeChatModel:
        def invoke(self, messages):
            return AIMessage(content="我可以帮你规划第一卷的冲突和人物弧光。")

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())

    profile = ModelProfile(
        owner_id=uuid4(),
        name="DeepSeek",
        provider_kind="openai-compatible",
        base_url="https://api.deepseek.com",
        api_key_ciphertext=encrypt_api_key("sk-test"),
        chat_model="deepseek-v4-pro",
        writing_model="deepseek-v4-pro",
        summary_model="deepseek-v4-pro",
        embedding_model="",
    )
    graph = build_agent_graph()
    result = graph.invoke(
        {
            "novel_id": uuid4(),
            "message": "我想写小说",
            "model_profile": profile,
        }
    )

    assert "规划" in result["response"]


def test_agent_chat_without_model_profile_prompts_configuration() -> None:
    graph = build_agent_graph()
    result = graph.invoke(
        {
            "novel_id": uuid4(),
            "message": "我想写小说",
        }
    )

    assert "Agent 配置" in result["response"]
