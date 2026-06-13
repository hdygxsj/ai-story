import ast
import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.context import ContextBudget, ContextPack, build_context_pack
from app.agent.model_runtime import build_chat_model
from app.agent.state import AgentState
from app.agent.tools import classify_agent_intent, get_agent_tools


def _build_agent_system_prompt(pack: ContextPack) -> str:
    labels = {
        "selected_text": "用户当前选中的段落",
        "current_document": "当前文档",
        "key_memory": "关键记忆",
        "structured_memory": "结构化素材",
        "neighboring_chapter": "相邻章节",
        "rag_result": "检索结果",
        "conversation_history": "对话历史",
    }
    lines = [
        "你是 AI 小说工坊的共创 Agent，帮助用户规划故事、改写段落、记录记忆和检索上下文。",
        "请使用与用户相同的语言回复，给出具体、可执行的建议。",
    ]
    for item in pack.items:
        if item.source == "user_instruction":
            continue
        label = labels.get(item.source, item.source)
        lines.append(f"【{label}】\n{item.text}")
    return "\n\n".join(lines)


def _message_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
        return "".join(parts).strip()
    return str(content).strip()


def _invoke_chat_model(state: AgentState, pack: ContextPack) -> dict[str, Any]:
    model_profile = state.get("model_profile")
    if model_profile is None:
        return {
            "response": "请先在 Agent 配置中为当前小说绑定并保存可用的对话模型。",
            "context_status": pack.status_messages,
            "proposed_payload": None,
        }

    try:
        model = build_chat_model(model_profile, purpose="chat")
        ai_message = model.invoke(
            [
                SystemMessage(content=_build_agent_system_prompt(pack)),
                HumanMessage(content=state["message"]),
            ]
        )
    except Exception as exc:
        return {
            "response": f"对话模型调用失败：{exc}",
            "context_status": pack.status_messages,
            "proposed_payload": None,
        }

    response = _message_text(ai_message.content)
    return {
        "response": response or "模型未返回内容，请稍后重试。",
        "context_status": pack.status_messages,
        "proposed_payload": None,
    }


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
        **_invoke_chat_model(state, pack),
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
        return _invoke_chat_model(state, pack)

    tool_result = _parse_tool_content(tool_messages[-1].content)
    if tool_result.get("action_type") == "rewrite_selection":
        return {
            "response": str(tool_result["message"]),
            "proposed_payload": tool_result["payload"],
        }
    if tool_result.get("action_type") == "memory_saved":
        return {
            "response": str(tool_result["message"]),
            "proposed_payload": None,
        }

    return {
        "response": "I prepared an Agent proposal for review.",
        "proposed_payload": tool_result.get("payload"),
    }


def build_agent_graph(
    tools: list | None = None,
    checkpointer=None,
):
    tool_list = tools or get_agent_tools()
    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tool_list))
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "finalize"})
    graph.add_edge("tools", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
