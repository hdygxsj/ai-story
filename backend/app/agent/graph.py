from langgraph.graph import END, StateGraph

from app.agent.context import ContextBudget, build_context_pack
from app.agent.state import AgentState
from app.agent.tools import classify_agent_intent, draft_rewrite


def agent_node(state: AgentState) -> AgentState:
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
        replacement = draft_rewrite(state["selected_text"], state["message"])
        state["response"] = "I drafted a tenser replacement. Please confirm before I apply it."
        state["context_status"] = pack.status_messages
        state["proposed_payload"] = {
            "document_id": str(state["document_id"]),
            "selected_text": state["selected_text"],
            "replacement_text": replacement,
        }
        return state

    state["response"] = "I can help shape the novel. Tell me what to create, rewrite, or remember."
    state["context_status"] = pack.status_messages
    state["proposed_payload"] = None
    return state


def build_agent_graph():
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.set_entry_point("agent")
    graph.add_edge("agent", END)
    return graph.compile()
