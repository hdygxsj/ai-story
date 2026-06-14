import ast
import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph

from app.agent.atomic_ops import ATOMIC_OPS_GUIDANCE
from app.agent.context import ContextPack
from app.agent.model_runtime import build_chat_model
from app.agent.state import AgentState
from app.agent.tools import classify_agent_intent, get_agent_tools
from app.models import ModelProfile

_MEMORY_GUIDANCE = (
    "当对话中出现会影响后续创作的持久事实、约束、偏好、角色状态或剧情信息时，"
    "调用 save_key_memory 直接保存，无需用户审批。不要保存临时信息或重复内容。"
)
_MATERIAL_GUIDANCE = (
    "当用户要求创建、修改、删除创作资产、时间线、角色状态或人物关系时，"
    "必须直接调用相应 list/create/update/delete 工具，无需用户确认。"
    "清理旧版或重复素材时，自行调用 delete_creative_asset 或 delete_creative_assets，"
    "不要要求用户手动删除。修改或删除前先 list 获取 id。"
)
_DESTRUCTIVE_WRITE_GUIDANCE = "propose_document_update 等需用户确认；write_document_content 等原子写入会立即生效。"
_EXPLICIT_WRITE_GUIDANCE = (
    "当前明确写入指令优先于历史规划、讨论和待办。用户要求写入章节正文时，"
    "不要继续规划、复述大纲或改写其他章节方案；必须调用章节或正文写入工具完成任务。"
    "先用 list_workspace_nodes 确认目标章节：已有章节调用 read_document 后使用 "
    "write_document_content，缺失章节使用 create_chapter_with_content。多章请求要逐章处理，"
    "只有工具成功后才能声称已写入。"
)


def _default_system_prompt(state: AgentState) -> str:
    novel_id = state.get("novel_id")
    lines = [
        "你是 AI 小说工坊的共创 Agent，通过组合原子工具完成用户的复杂创作需求。",
        "请使用与用户相同的语言回复。",
        ATOMIC_OPS_GUIDANCE.strip(),
        _MEMORY_GUIDANCE,
        _MATERIAL_GUIDANCE,
        _DESTRUCTIVE_WRITE_GUIDANCE,
    ]
    if novel_id is not None:
        lines.append(f"当前小说 ID: {novel_id}")
    return "\n".join(lines)


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
        "你是 AI 小说工坊的共创 Agent，通过组合原子工具完成用户的复杂创作需求。",
        "请使用与用户相同的语言回复。",
        ATOMIC_OPS_GUIDANCE.strip(),
        _MEMORY_GUIDANCE,
        _MATERIAL_GUIDANCE,
        _DESTRUCTIVE_WRITE_GUIDANCE,
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


def _tool_side_effects(tool_result: dict[str, Any]) -> dict[str, Any]:
    effects: dict[str, Any] = {}
    if tool_result.get("workspace_diff") is not None:
        effects["workspace_diff"] = tool_result["workspace_diff"]
    if tool_result.get("workspace_nodes") is not None:
        effects["workspace_nodes"] = tool_result["workspace_nodes"]
    if tool_result.get("confirmation_id") is not None:
        effects["confirmation_id"] = tool_result["confirmation_id"]
    if tool_result.get("action_type") == "rewrite_selection":
        effects["proposed_payload"] = tool_result.get("payload")
    if tool_result.get("novel_updated") is not None:
        effects["novel_updated"] = tool_result["novel_updated"]
    return effects


def _serialize_tool_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, default=str)


def _remove_incomplete_tool_call_history(messages: list[Any]) -> list[Any]:
    cleaned: list[Any] = []
    index = 0
    while index < len(messages):
        message = messages[index]
        if not isinstance(message, AIMessage) or not message.tool_calls:
            cleaned.append(message)
            index += 1
            continue

        expected_ids = {str(call.get("id", "")) for call in message.tool_calls}
        tool_messages: list[ToolMessage] = []
        cursor = index + 1
        while cursor < len(messages) and isinstance(messages[cursor], ToolMessage):
            tool_messages.append(messages[cursor])
            cursor += 1
        received_ids = {str(tool_message.tool_call_id) for tool_message in tool_messages}
        if expected_ids and expected_ids.issubset(received_ids):
            cleaned.append(message)
            cleaned.extend(tool_messages)
        index = cursor
    return cleaned


def build_agent_graph(
    tools: list | None = None,
    checkpointer=None,
    model_profile: ModelProfile | None = None,
):
    tool_list = tools or get_agent_tools()
    tools_by_name = {tool.name: tool for tool in tool_list}
    bound_model_profile = model_profile

    def tool_calls_from_state(state: AgentState) -> list[dict[str, Any]]:
        messages = list(state.get("messages", []))
        if not messages or not isinstance(messages[-1], AIMessage):
            return []
        return list(messages[-1].tool_calls)

    def tool_message(tool_call: dict[str, Any], result: Any) -> ToolMessage:
        tool_name = str(tool_call.get("name", ""))
        return ToolMessage(
            content=_serialize_tool_result(result),
            name=tool_name,
            tool_call_id=str(tool_call.get("id", tool_name)),
        )

    def sequential_tools_node_sync(state: AgentState) -> dict[str, Any]:
        tool_messages: list[ToolMessage] = []
        for tool_call in tool_calls_from_state(state):
            tool_name = str(tool_call.get("name", ""))
            tool = tools_by_name.get(tool_name)
            result: Any = (
                tool.invoke(tool_call.get("args", {}))
                if tool is not None
                else {"status": "error", "message": f"未知工具：{tool_name}"}
            )
            tool_messages.append(tool_message(tool_call, result))
        return {"messages": tool_messages}

    async def sequential_tools_node_async(state: AgentState) -> dict[str, Any]:
        tool_messages: list[ToolMessage] = []
        for tool_call in tool_calls_from_state(state):
            tool_name = str(tool_call.get("name", ""))
            tool = tools_by_name.get(tool_name)
            if tool is None:
                result: Any = {"status": "error", "message": f"未知工具：{tool_name}"}
            else:
                result = await tool.ainvoke(tool_call.get("args", {}))
            tool_messages.append(tool_message(tool_call, result))
        return {"messages": tool_messages}

    def prepare_agent_call(state: AgentState) -> tuple[list[Any], Any, str | None]:
        prior = _remove_incomplete_tool_call_history(list(state.get("messages", [])))
        intent = classify_agent_intent(state["message"], state.get("selected_text"))
        if (
            intent == "rewrite_selection"
            and state.get("selected_text")
            and state.get("document_id")
            and not any(isinstance(message, ToolMessage) for message in prior)
        ):
            messages = prior or [HumanMessage(content=state["message"])]
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
            return messages, None, "rewrite"

        model_profile = bound_model_profile
        tool_messages = [message for message in prior if isinstance(message, ToolMessage)]
        if model_profile is None:
            if tool_messages:
                return prior, None, "done"
            return [HumanMessage(content=state["message"])], None, "missing_model"

        system_prompt = state.get("system_prompt") or _default_system_prompt(state)
        if intent == "write_chapter_content":
            system_prompt = f"{system_prompt}\n\n{_EXPLICIT_WRITE_GUIDANCE}"
        if not prior:
            prior = [SystemMessage(content=system_prompt), HumanMessage(content=state["message"])]
        elif intent == "write_chapter_content":
            prior.insert(0, SystemMessage(content=_EXPLICIT_WRITE_GUIDANCE))

        model = build_chat_model(model_profile, purpose="chat").bind_tools(tool_list)
        return prior, model, None

    def agent_node_sync(state: AgentState) -> dict[str, Any]:
        prior, model, shortcut = prepare_agent_call(state)
        if shortcut == "rewrite":
            return {"messages": prior}
        if shortcut == "done":
            return {}
        if shortcut == "missing_model":
            return {"messages": prior, "response": "请先在 Agent 配置中为当前小说绑定并保存可用的对话模型。"}
        ai_message = model.invoke(prior)
        updates: dict[str, Any] = {"messages": [ai_message]}
        if not ai_message.tool_calls:
            updates["response"] = _message_text(ai_message.content) or "操作已完成。"
        return updates

    async def agent_node_async(state: AgentState) -> dict[str, Any]:
        prior, model, shortcut = prepare_agent_call(state)
        if shortcut == "rewrite":
            return {"messages": prior}
        if shortcut == "done":
            return {}
        if shortcut == "missing_model":
            return {"messages": prior, "response": "请先在 Agent 配置中为当前小说绑定并保存可用的对话模型。"}

        ai_message = None
        if hasattr(model, "astream"):
            async for chunk in model.astream(prior):
                ai_message = chunk if ai_message is None else ai_message + chunk
        else:
            ai_message = model.invoke(prior)
        if ai_message is None:
            ai_message = AIMessage(content="")
        updates: dict[str, Any] = {"messages": [ai_message]}
        if not ai_message.tool_calls:
            updates["response"] = _message_text(ai_message.content) or "操作已完成。"
        return updates

    def finalize_node(state: AgentState) -> dict[str, Any]:
        tool_messages = [message for message in state.get("messages", []) if isinstance(message, ToolMessage)]
        if not tool_messages:
            if state.get("response"):
                return {}
            return {"response": "我没有拿到工具结果，请换个说法再试一次。"}

        tool_results = [_parse_tool_content(message.content) for message in tool_messages]
        tool_result = tool_results[-1]
        if tool_result.get("action_type") == "rewrite_selection":
            return {
                "response": str(tool_result.get("message", "我已草拟改写方案，请确认后再应用。")),
                "proposed_payload": tool_result.get("payload"),
            }
        if tool_result.get("action_type") == "memory_saved":
            return {
                "response": str(tool_result.get("message", "已保存关键记忆。")),
                "proposed_payload": None,
            }

        message = state.get("response") or tool_result.get("message")
        if not message:
            message = "操作已完成。" if tool_result.get("status") == "ok" else "操作失败，请检查参数后重试。"

        effects: dict[str, Any] = {}
        for result in tool_results:
            effects.update(_tool_side_effects(result))
        return {
            "response": str(message),
            **effects,
        }

    def route_after_agent(state: AgentState) -> str:
        messages = list(state.get("messages", []))
        if messages and isinstance(messages[-1], AIMessage) and messages[-1].tool_calls:
            return "tools"
        return "finalize"

    graph = StateGraph(AgentState)
    graph.add_node("agent", RunnableLambda(agent_node_sync, afunc=agent_node_async))
    graph.add_node("tools", RunnableLambda(sequential_tools_node_sync, afunc=sequential_tools_node_async))
    graph.add_node("finalize", finalize_node)
    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", route_after_agent, {"tools": "tools", "finalize": "finalize"})
    graph.add_edge("tools", "agent")
    graph.add_edge("finalize", END)
    return graph.compile(checkpointer=checkpointer)
