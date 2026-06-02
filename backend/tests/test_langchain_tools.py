from uuid import uuid4

from langchain_core.tools import BaseTool

from app.agent.graph import build_agent_graph
from app.agent.tools import get_agent_tools


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
