import ast
import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.context import ContextBudget, build_context_pack
from app.agent.state import AgentState
from app.agent.tools import classify_agent_intent, get_agent_tools


def agent_node(state: AgentState) -> dict[str, Any]:
    pack = build_context_pack(
        user_instruction=state["message"],
        current_document_text="",
        selected_text=state.get("selected_text"),
        key_memories=[],
        structured_memories=[],
        neighboring_chapters=[],
        rag_results=[],
        budget=ContextBudget(max_tokens=8000, response_tokens=1000),
    )
    intent = classify_agent_intent(state["message"], state.get("selected_text"))
    if intent == "rewrite_selection" and state.get("selected_text") and state.get("document_id"):
        messages = list(state.get("messages", []))
        if not messages:
            messages.append(HumanMessage(content=state["message"]))
        messages.append(
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "propose_rewrite",
                        "args": {
                            "document_id": str(state["document_id"]),
                            "selected_text": state["selected_text"],
                            "instruction": state["message"],
                        },
                        "id": "call_propose_rewrite",
                    }
                ],
            )
        )
        return {"messages": messages, "context_status": pack.status_messages}

    return {
        "messages": [*state.get("messages", []), HumanMessage(content=state["message"])],
        "response": "I can help shape the novel. Tell me what to create, rewrite, or remember.",
        "context_status": pack.status_messages,
        "proposed_payload": None,
    }


def _parse_tool_content(content: Any) -> dict[str, Any]:
    if isinstance(content, dict):
        return content
    if not isinstance(content, str):
        return {}
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        parsed = ast.literal_eval(content)
    return parsed if isinstance(parsed, dict) else {}


def finalize_node(state: AgentState) -> dict[str, Any]:
    if state.get("response"):
        return {}

    tool_messages = [message for message in state.get("messages", []) if isinstance(message, ToolMessage)]
    if not tool_messages:
        return {
            "response": "I can help shape the novel. Tell me what to create, rewrite, or remember.",
            "proposed_payload": None,
        }

    tool_result = _parse_tool_content(tool_messages[-1].content)
    if tool_result.get("action_type") == "rewrite_selection":
        return {
            "response": str(tool_result["message"]),
            "proposed_payload": tool_result["payload"],
        }

    return {
        "response": "I prepared an Agent proposal for review.",
        "proposed_payload": tool_result.get("payload"),
    }


def build_agent_graph():
    tools = get_agent_tools()
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "finalize"})
    graph.add_edge("tools", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()
