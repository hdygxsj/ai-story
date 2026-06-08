from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool

from app.agent.graph import build_agent_graph
from app.agent.tools import get_agent_tools
from app.core.crypto import encrypt_api_key
from app.models import ModelProfile


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
        "propose_key_memory",
        "create_character_asset",
        "create_world_rule",
        "create_timeline_event",
        "update_character_state",
        "propose_workspace_change",
    }.issubset(tool_names)


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
