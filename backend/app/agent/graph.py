import ast
import json
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.graph import END, StateGraph

from app.agent.atomic_ops import ATOMIC_OPS_GUIDANCE
from app.agent.context import ContextPack, estimate_tokens
from app.agent.model_runtime import build_chat_model
from app.agent.state import AgentState
from app.agent.tools import MATH_CALCULATION_GUIDANCE, get_agent_tools
from app.models import ModelProfile

_MEMORY_GUIDANCE = (
    "当对话中出现会影响后续创作的持久事实、约束、偏好、角色状态或剧情信息时，"
    "调用 save_key_memory 直接保存，无需用户审批。不要保存临时信息或重复内容。"
)
_MATERIAL_GUIDANCE = (
    "当用户要求创建、修改、删除创作资产、时间线、角色状态或人物关系时，"
    "必须直接调用相应 list/create/update/delete 工具，无需用户确认。"
    "角色状态：同一角色 + 同一 scope 只保留一条记录，更新时用 update_character_state 并传 state_id；"
    "scope=current 表示最新状态，章节快照请用 chapter_3 等独立 scope，不要重复创建。"
    "时间线：同一 title + event_time 只保留一条，更新时用 update_timeline_event 并传 event_id；"
    "调整显示顺序时先 list_timeline_events，再调用 reorder_timeline_events 传入按目标顺序排列的 event_id 列表，"
    "也可用 update_timeline_event 设置单个事件的 position；"
    "未设置 position 的事件仍按卷号/时间标签自动排序并排在已指定 position 的事件之后。"
    "清理旧版或重复素材时，自行调用 delete_creative_asset 或 delete_creative_assets，"
    "不要要求用户手动删除。修改或删除前先 list 获取 id。"
)
_DESTRUCTIVE_WRITE_GUIDANCE = "propose_document_update 等需用户确认；write_document_content 等原子写入会立即生效。"
_CURRENT_REQUEST_GUIDANCE = (
    "始终优先处理用户当前消息，不要被历史对话中的旧任务、旧规划或待办带偏。"
    "根据当前需求自主规划并组合原子工具；不要套用固定业务流程。"
    "涉及外部状态变更时，只有工具成功返回后才能声称已经完成。"
)
_REPEATED_TOOL_CALL_RESPONSE = "检测到重复工具调用，已停止继续执行；上一次工具调用结果已保留。"
_CONTEXT_COMPRESSION_GUIDANCE = (
    "本轮工具调用历史因上下文接近上限已自动压缩；"
    "请把仍需保留的关键事实写入 save_key_memory，然后继续当前任务。"
)
_MIN_FULL_TOOL_ROUNDS = 3
_TOOL_RESULT_TRUNCATE_TOKENS = 120
_RESPONSE_TOKEN_RESERVE = 4096


def _default_system_prompt(state: AgentState) -> str:
    novel_id = state.get("novel_id")
    lines = [
        "你是 AI 小说工坊的共创 Agent，通过组合原子工具完成用户的复杂创作需求。",
        "请使用与用户相同的语言回复。",
        ATOMIC_OPS_GUIDANCE.strip(),
        MATH_CALCULATION_GUIDANCE,
        _MEMORY_GUIDANCE,
        _MATERIAL_GUIDANCE,
        _DESTRUCTIVE_WRITE_GUIDANCE,
        _CURRENT_REQUEST_GUIDANCE,
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
        MATH_CALCULATION_GUIDANCE,
        _MEMORY_GUIDANCE,
        _MATERIAL_GUIDANCE,
        _DESTRUCTIVE_WRITE_GUIDANCE,
        _CURRENT_REQUEST_GUIDANCE,
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


def _tool_call_batch_signature(tool_calls: list[dict[str, Any]]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (
            str(tool_call.get("name", "")),
            json.dumps(tool_call.get("args", {}), ensure_ascii=False, sort_keys=True, default=str),
        )
        for tool_call in tool_calls
    )


def _last_tool_call_batch(messages: list[Any]) -> list[dict[str, Any]]:
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.tool_calls:
            return list(message.tool_calls)
    return []


def _estimate_messages_tokens(messages: list[Any]) -> int:
    total = 0
    for message in messages:
        if isinstance(message, (SystemMessage, HumanMessage, AIMessage)):
            content = _message_text(message.content)
            if isinstance(message, AIMessage) and message.tool_calls:
                content += json.dumps(message.tool_calls, ensure_ascii=False, sort_keys=True, default=str)
            total += estimate_tokens(content)
        elif isinstance(message, ToolMessage):
            total += estimate_tokens(str(message.content))
    return total


def _truncate_tool_content(content: str, max_tokens: int) -> str:
    max_chars = max(4, max_tokens * 4)
    if len(content) <= max_chars:
        return content
    return content[: max_chars - 1].rstrip() + "…"


def _compress_tool_round_history(
    messages: list[Any],
    *,
    max_tokens: int,
    response_tokens: int = _RESPONSE_TOKEN_RESERVE,
) -> tuple[list[Any], bool]:
    available = max(8000, max_tokens - response_tokens)
    threshold = int(available * 0.85)
    if _estimate_messages_tokens(messages) <= threshold:
        return messages, False

    result = list(messages)
    tool_message_indices = [index for index, message in enumerate(result) if isinstance(message, ToolMessage)]
    if not tool_message_indices:
        return messages, False

    protected = set(tool_message_indices[-_MIN_FULL_TOOL_ROUNDS:])
    compressed = False
    for index in tool_message_indices:
        if index in protected:
            continue
        message = result[index]
        original = str(message.content)
        shortened = _truncate_tool_content(original, _TOOL_RESULT_TRUNCATE_TOKENS)
        if shortened != original:
            result[index] = ToolMessage(
                content=shortened,
                name=message.name,
                tool_call_id=message.tool_call_id,
            )
            compressed = True

    while _estimate_messages_tokens(result) > threshold:
        last_protected = max(protected) if protected else -1
        found = False
        for index in tool_message_indices:
            if index >= last_protected:
                continue
            message = result[index]
            content = str(message.content)
            if len(content) <= 50:
                continue
            result[index] = ToolMessage(
                content=_truncate_tool_content(content, max(30, _TOOL_RESULT_TRUNCATE_TOKENS // 2)),
                name=message.name,
                tool_call_id=message.tool_call_id,
            )
            compressed = True
            found = True
        if not found:
            break

    return result, compressed


def _inject_context_compression_guidance(messages: list[Any]) -> list[Any]:
    if not messages or not isinstance(messages[0], SystemMessage):
        return [SystemMessage(content=_CONTEXT_COMPRESSION_GUIDANCE), *messages]
    system = messages[0]
    guidance = _CONTEXT_COMPRESSION_GUIDANCE
    content = _message_text(system.content)
    if guidance in content:
        return messages
    return [
        SystemMessage(content=f"{content}\n\n{guidance}".strip()),
        *messages[1:],
    ]


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
        if (
            state.get("selected_text")
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
        if _CURRENT_REQUEST_GUIDANCE not in system_prompt:
            system_prompt = f"{system_prompt}\n\n{_CURRENT_REQUEST_GUIDANCE}"
        if not prior:
            prior = [
                SystemMessage(content=system_prompt),
                *list(state.get("history_messages", [])),
                HumanMessage(content=state["message"]),
            ]

        prior, compressed = _compress_tool_round_history(
            prior,
            max_tokens=model_profile.context_window or 128000,
        )
        if compressed:
            prior = _inject_context_compression_guidance(prior)

        model = build_chat_model(model_profile, purpose="chat").bind_tools(tool_list)
        return prior, model, None

    def agent_updates(prior: list[Any], ai_message: AIMessage) -> dict[str, Any]:
        if ai_message.tool_calls:
            previous_calls = _last_tool_call_batch(prior)
            if previous_calls and _tool_call_batch_signature(ai_message.tool_calls) == _tool_call_batch_signature(
                previous_calls
            ):
                return {
                    "messages": [AIMessage(content=_REPEATED_TOOL_CALL_RESPONSE)],
                    "response": _REPEATED_TOOL_CALL_RESPONSE,
                }
            return {"messages": [ai_message]}
        return {
            "messages": [ai_message],
            "response": _message_text(ai_message.content) or "操作已完成。",
        }

    def agent_node_sync(state: AgentState) -> dict[str, Any]:
        prior, model, shortcut = prepare_agent_call(state)
        if shortcut == "rewrite":
            return {"messages": prior}
        if shortcut == "done":
            return {}
        if shortcut == "missing_model":
            return {"messages": prior, "response": "请先在 Agent 配置中为当前小说绑定并保存可用的对话模型。"}
        ai_message = model.invoke(prior)
        return agent_updates(prior, ai_message)

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
        return agent_updates(prior, ai_message)

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
