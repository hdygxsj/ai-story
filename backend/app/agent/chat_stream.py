import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import _build_agent_system_prompt, _message_text, build_agent_graph
from app.agent.model_runtime import build_chat_model
from app.agent.tools import classify_agent_intent
from app.models import ModelProfile, Novel
from app.services.context_assembly import assemble_context


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def stream_agent_events(
    session: AsyncSession,
    *,
    novel: Novel,
    conversation_id: UUID,
    document_id: UUID | None,
    message: str,
    selected_text: str | None,
    model_profile: ModelProfile | None,
    user_message_id: UUID | None = None,
) -> AsyncIterator[str]:
    assembled = await assemble_context(
        session,
        novel=novel,
        conversation_id=conversation_id,
        document_id=document_id,
        selected_text=selected_text,
        user_message=message,
        model_profile=model_profile,
        message_id=user_message_id,
    )
    pack = assembled.pack
    intent = classify_agent_intent(message, selected_text)

    if intent == "rewrite_selection" and selected_text and document_id:
        graph = build_agent_graph()
        result = graph.invoke(
            {
                "novel_id": novel.id,
                "document_id": document_id,
                "message": message,
                "model_profile": model_profile,
                "selected_text": selected_text,
            }
        )
        response = result.get("response", "")
        if response:
            yield _sse({"type": "delta", "content": response})
        yield _sse(
            {
                "type": "done",
                "message": response,
                "context_status": assembled.status_messages,
                "context_detail": assembled.context_detail.model_dump(mode="json"),
                "confirmation": None,
                "proposed_payload": result.get("proposed_payload"),
                "workspace_diff": None,
                "workspace_nodes": None,
            }
        )
        return

    if model_profile is None:
        response = "请先在 Agent 配置中为当前小说绑定并保存可用的对话模型。"
        yield _sse({"type": "delta", "content": response})
        yield _sse(
            {
                "type": "done",
                "message": response,
                "context_status": assembled.status_messages,
                "context_detail": assembled.context_detail.model_dump(mode="json"),
                "confirmation": None,
                "proposed_payload": None,
                "workspace_diff": None,
                "workspace_nodes": None,
            }
        )
        return

    try:
        model = build_chat_model(model_profile, purpose="chat")
        llm_messages = [
            SystemMessage(content=_build_agent_system_prompt(pack)),
            *assembled.history_messages,
            HumanMessage(content=message),
        ]
        chunks: list[str] = []
        async for chunk in model.astream(llm_messages):
            text = _message_text(getattr(chunk, "content", chunk))
            if not text:
                continue
            chunks.append(text)
            yield _sse({"type": "delta", "content": text})
        response = "".join(chunks).strip() or "模型未返回内容，请稍后重试。"
        yield _sse(
            {
                "type": "done",
                "message": response,
                "context_status": assembled.status_messages,
                "context_detail": assembled.context_detail.model_dump(mode="json"),
                "confirmation": None,
                "proposed_payload": None,
                "workspace_diff": None,
                "workspace_nodes": None,
            }
        )
    except Exception as exc:
        response = f"对话模型调用失败：{exc}"
        yield _sse({"type": "delta", "content": response})
        yield _sse(
            {
                "type": "done",
                "message": response,
                "context_status": assembled.status_messages,
                "context_detail": assembled.context_detail.model_dump(mode="json"),
                "confirmation": None,
                "proposed_payload": None,
                "workspace_diff": None,
                "workspace_nodes": None,
            }
        )
