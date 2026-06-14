import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.graph import _build_agent_system_prompt
from app.agent.context import ContextPack
from app.agent.prompts import append_agent_runtime_guidance
from app.agent.runtime import stream_agent_graph
from app.models import ModelProfile, Novel
from app.services.context_assembly import assemble_context


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(jsonable_encoder(payload), ensure_ascii=False)}\n\n"


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
    if model_profile is None and not selected_text:
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

    system_pack = ContextPack(
        items=[item for item in pack.items if item.source != "conversation_history"],
        estimated_tokens=pack.estimated_tokens,
        usage_ratio=pack.usage_ratio,
        status_messages=pack.status_messages,
    )
    system_prompt = append_agent_runtime_guidance(
        _build_agent_system_prompt(system_pack),
        novel_id=novel.id,
        document_id=document_id,
    )

    result: dict[str, Any] = {}
    streamed_content = ""
    async for event_type, payload in stream_agent_graph(
        session,
        state={
            "novel_id": novel.id,
            "document_id": document_id,
            "message": message,
            "selected_text": selected_text,
            "history_messages": assembled.history_messages,
            "system_prompt": system_prompt,
        },
        model_profile=model_profile,
        owner_id=novel.owner_id,
        novel_id=novel.id,
        conversation_id=conversation_id,
    ):
        if event_type == "delta":
            streamed_content += str(payload)
            yield _sse({"type": "delta", "content": str(payload)})
        elif event_type == "reasoning":
            yield _sse({"type": "reasoning", "content": str(payload)})
        elif event_type == "tool_call":
            yield _sse({"type": "tool_call", **(payload if isinstance(payload, dict) else {})})
        else:
            result = payload if isinstance(payload, dict) else {}

    response = str(result.get("response", ""))
    if response and not streamed_content:
        yield _sse({"type": "delta", "content": response})
    yield _sse(
        {
            "type": "done",
            "message": response,
            "context_status": assembled.status_messages,
            "context_detail": assembled.context_detail.model_dump(mode="json"),
            "confirmation": None,
            "confirmation_id": result.get("confirmation_id"),
            "proposed_payload": result.get("proposed_payload"),
            "workspace_diff": result.get("workspace_diff"),
            "workspace_nodes": result.get("workspace_nodes"),
            "novel_updated": result.get("novel_updated"),
            "tool_calls": result.get("tool_calls") or [],
        }
    )
