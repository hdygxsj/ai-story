import asyncio
import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chat_stream import _sse, stream_agent_events
from app.agent.context import ContextPack
from app.agent.stream_errors import format_agent_stream_error
from app.agent.graph import _build_agent_system_prompt
from app.agent.prompts import append_agent_runtime_guidance
from app.agent.runtime import invoke_agent_graph
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Conversation, Document, Message, ModelProfile, PendingConfirmation, User
from app.schemas.agent import AgentMessageRequest, AgentMessageResponse
from app.services.context_assembly import assemble_context
from app.services.conversations import append_message, maybe_auto_title_conversation, resolve_conversation_for_message
from app.services.document_actions import build_confirmation_responses
from app.services.novels import get_owned_novel
from app.services.workspace_actions import load_workspace_nodes

router = APIRouter(prefix="/novels/{novel_id}/agent", tags=["agent"])


async def persist_interrupted_assistant_message(
    session: AsyncSession,
    *,
    conversation: Conversation,
    content: str,
    tool_calls: list[dict[str, Any]] | None = None,
    reasoning_content: str | None = None,
) -> Message | None:
    if not content.strip():
        return None
    metadata: dict[str, Any] = {"interrupted": True}
    if tool_calls:
        metadata["tool_calls"] = tool_calls
    if reasoning_content:
        metadata["reasoning_content"] = reasoning_content
    return await append_message(
        session,
        conversation=conversation,
        role="assistant",
        content=content,
        metadata=metadata,
    )


async def _get_novel_model_profile(
    session: AsyncSession,
    novel,
    owner_id: UUID,
) -> ModelProfile | None:
    if novel.default_model_profile_id is None:
        return None
    return await session.scalar(
        select(ModelProfile).where(
            ModelProfile.id == novel.default_model_profile_id,
            ModelProfile.owner_id == owner_id,
        )
    )


@router.post("/messages", response_model=AgentMessageResponse)
async def send_agent_message(
    novel_id: UUID,
    payload: AgentMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> AgentMessageResponse:
    novel = await get_owned_novel(session, current_user, novel_id)
    if payload.document_id is not None:
        document = await session.scalar(
            select(Document).where(Document.id == payload.document_id, Document.novel_id == novel_id)
        )
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    model_profile = await _get_novel_model_profile(session, novel, current_user.id)
    conversation = await resolve_conversation_for_message(
        session,
        novel_id=novel_id,
        user_id=current_user.id,
        conversation_id=payload.conversation_id,
        message=payload.message,
    )
    conversation = await maybe_auto_title_conversation(
        session,
        conversation=conversation,
        message=payload.message,
    )
    user_message = await append_message(
        session,
        conversation=conversation,
        role="user",
        content=payload.message,
    )

    assembled = await assemble_context(
        session,
        novel=novel,
        conversation_id=conversation.id,
        document_id=payload.document_id,
        selected_text=payload.selected_text,
        user_message=payload.message,
        model_profile=model_profile,
        message_id=user_message.id,
    )
    system_pack = ContextPack(
        items=[item for item in assembled.pack.items if item.source != "conversation_history"],
        estimated_tokens=assembled.pack.estimated_tokens,
        usage_ratio=assembled.pack.usage_ratio,
        status_messages=assembled.pack.status_messages,
    )
    system_prompt = append_agent_runtime_guidance(
        _build_agent_system_prompt(system_pack),
        novel_id=novel.id,
        document_id=payload.document_id,
    )

    result = await invoke_agent_graph(
        session,
        state={
            "novel_id": novel_id,
            "document_id": payload.document_id,
            "message": payload.message,
            "selected_text": payload.selected_text,
            "history_messages": assembled.history_messages,
            "system_prompt": system_prompt,
        },
        model_profile=model_profile,
        owner_id=current_user.id,
        novel_id=novel_id,
        conversation_id=conversation.id,
    )

    confirmation = None
    if result.get("confirmation_id"):
        confirmation = await session.scalar(
            select(PendingConfirmation).where(
                PendingConfirmation.id == UUID(result["confirmation_id"]),
                PendingConfirmation.novel_id == novel_id,
            )
        )
    elif result.get("proposed_payload"):
        confirmation = PendingConfirmation(
            novel_id=novel_id,
            action_type="rewrite_selection",
            payload=result["proposed_payload"],
        )
        session.add(confirmation)
        await session.commit()
        await session.refresh(confirmation)

    await append_message(
        session,
        conversation=conversation,
        role="assistant",
        content=result["response"],
    )
    workspace_nodes = None
    if result.get("workspace_nodes"):
        workspace_nodes = await load_workspace_nodes(session, novel_id)
    return AgentMessageResponse(
        message=result["response"],
        context_status=assembled.status_messages,
        context_detail=assembled.context_detail,
        conversation_id=conversation.id,
        confirmation=confirmation,
        workspace_diff=result.get("workspace_diff"),
        workspace_nodes=workspace_nodes,
        novel_updated=result.get("novel_updated"),
    )


@router.post("/messages/stream")
async def stream_agent_message(
    request: Request,
    novel_id: UUID,
    payload: AgentMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    novel = await get_owned_novel(session, current_user, novel_id)
    if payload.document_id is not None:
        document = await session.scalar(
            select(Document).where(Document.id == payload.document_id, Document.novel_id == novel_id)
        )
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    model_profile = await _get_novel_model_profile(session, novel, current_user.id)
    conversation = await resolve_conversation_for_message(
        session,
        novel_id=novel_id,
        user_id=current_user.id,
        conversation_id=payload.conversation_id,
        message=payload.message,
    )
    conversation = await maybe_auto_title_conversation(
        session,
        conversation=conversation,
        message=payload.message,
    )
    user_message = await append_message(
        session,
        conversation=conversation,
        role="user",
        content=payload.message,
    )

    streamed_assistant_content = ""
    streamed_reasoning_content = ""
    streamed_tool_calls: list[dict[str, Any]] = []
    assistant_message_persisted = False

    async def persist_interrupted_response() -> None:
        nonlocal assistant_message_persisted
        if assistant_message_persisted:
            return
        message = await persist_interrupted_assistant_message(
            session,
            conversation=conversation,
            content=streamed_assistant_content,
            tool_calls=streamed_tool_calls,
            reasoning_content=streamed_reasoning_content,
        )
        if message is not None:
            assistant_message_persisted = True

    async def event_stream():
        try:
            yield _sse({"type": "meta", "conversation_id": str(conversation.id)})
            async for raw_event in _stream_agent_response():
                if await request.is_disconnected():
                    await persist_interrupted_response()
                    return
                yield raw_event
        except asyncio.CancelledError:
            await persist_interrupted_response()
            return
        except Exception as exc:
            yield _sse({"type": "error", "message": format_agent_stream_error(exc)})

    async def _stream_agent_response():
        nonlocal assistant_message_persisted, streamed_assistant_content, streamed_reasoning_content
        async for raw_event in stream_agent_events(
            session,
            novel=novel,
            conversation_id=conversation.id,
            document_id=payload.document_id,
            message=payload.message,
            selected_text=payload.selected_text,
            model_profile=model_profile,
            user_message_id=user_message.id,
        ):
            if await request.is_disconnected():
                return

            if not raw_event.startswith("data: "):
                yield raw_event
                continue

            event_payload: dict[str, Any] = json.loads(raw_event[6:].strip())
            if event_payload.get("type") == "delta":
                streamed_assistant_content += str(event_payload.get("content", ""))
            elif event_payload.get("type") == "reasoning":
                streamed_reasoning_content += str(event_payload.get("content", ""))
            elif event_payload.get("type") == "tool_call":
                record = {key: value for key, value in event_payload.items() if key != "type"}
                if record:
                    for index, existing in enumerate(streamed_tool_calls):
                        if existing.get("id") == record.get("id"):
                            streamed_tool_calls[index] = record
                            break
                    else:
                        streamed_tool_calls.append(record)

            if event_payload.get("type") == "done":
                final_message = str(event_payload.get("message", ""))
                tool_calls = event_payload.get("tool_calls") or []
                if final_message:
                    metadata: dict[str, Any] = {}
                    if tool_calls:
                        metadata["tool_calls"] = tool_calls
                    if streamed_reasoning_content:
                        metadata["reasoning_content"] = streamed_reasoning_content
                    await append_message(
                        session,
                        conversation=conversation,
                        role="assistant",
                        content=final_message,
                        metadata=metadata or None,
                    )
                    assistant_message_persisted = True
                event_payload["conversation_id"] = str(conversation.id)
                if event_payload.get("proposed_payload"):
                    confirmation = PendingConfirmation(
                        novel_id=novel_id,
                        action_type="rewrite_selection",
                        payload=event_payload["proposed_payload"],
                    )
                    session.add(confirmation)
                    await session.commit()
                    await session.refresh(confirmation)
                    built = await build_confirmation_responses(session, [confirmation])
                    event_payload["confirmation"] = built[0]
                    event_payload.pop("proposed_payload", None)
                elif event_payload.get("confirmation_id"):
                    confirmation = await session.scalar(
                        select(PendingConfirmation).where(
                            PendingConfirmation.id == UUID(event_payload["confirmation_id"]),
                            PendingConfirmation.novel_id == novel_id,
                        )
                    )
                    if confirmation is not None:
                        built = await build_confirmation_responses(session, [confirmation])
                        event_payload["confirmation"] = built[0]
                    event_payload.pop("confirmation_id", None)
                yield _sse(event_payload)
                continue

            yield raw_event

    return StreamingResponse(event_stream(), media_type="text/event-stream")
