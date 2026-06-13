import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chat_stream import _sse, stream_agent_events
from app.agent.stream_errors import format_agent_stream_error
from app.agent.graph import _build_agent_system_prompt
from app.agent.runtime import invoke_agent_graph
from app.agent.tools import classify_agent_intent
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Document, ModelProfile, PendingConfirmation, User
from app.schemas.agent import AgentMessageRequest, AgentMessageResponse
from app.schemas.confirmation import ConfirmationResponse
from app.schemas.workspace import WorkspaceNodeResponse
from app.services.context_assembly import assemble_context
from app.services.conversations import append_message, resolve_conversation_for_message
from app.services.memory import create_memory_item
from app.services.novels import get_owned_novel
from app.services.workspace_actions import cleanup_workspace_folders, load_workspace_nodes, organize_workspace_tree

router = APIRouter(prefix="/novels/{novel_id}/agent", tags=["agent"])


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
    await append_message(
        session,
        conversation=conversation,
        role="user",
        content=payload.message,
    )

    intent = classify_agent_intent(payload.message, payload.selected_text)
    if intent in {"organize_workspace", "cleanup_workspace"}:
        if intent == "cleanup_workspace":
            action_result = await cleanup_workspace_folders(
                session, novel_id=novel_id, message=payload.message
            )
        else:
            action_result = await organize_workspace_tree(session, novel_id=novel_id)
        message = str(action_result.get("message", "操作已完成。"))
        workspace_diff = action_result.get("workspace_diff")
        workspace_nodes = await load_workspace_nodes(session, novel_id)
        await append_message(session, conversation=conversation, role="assistant", content=message)
        return AgentMessageResponse(
            message=message,
            context_status=[],
            conversation_id=conversation.id,
            confirmation=None,
            workspace_diff=workspace_diff,
            workspace_nodes=workspace_nodes,
        )

    assembled = await assemble_context(
        session,
        novel=novel,
        conversation_id=conversation.id,
        document_id=payload.document_id,
        selected_text=payload.selected_text,
        user_message=payload.message,
        model_profile=model_profile,
    )
    system_prompt = (
        _build_agent_system_prompt(assembled.pack)
        + f"\n\n当前小说 ID: {novel.id}"
        + "\n可用工具包括：章节树增删改查、完整章节写入、记忆读写、素材与时间线整理。需要实际操作时请调用工具。"
    )

    result = await invoke_agent_graph(
        session,
        state={
            "novel_id": novel_id,
            "document_id": payload.document_id,
            "message": payload.message,
            "selected_text": payload.selected_text,
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
    )


@router.post("/messages/stream")
async def stream_agent_message(
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
    user_message = await append_message(
        session,
        conversation=conversation,
        role="user",
        content=payload.message,
    )

    async def event_stream():
        try:
            async for raw_event in _stream_agent_response():
                yield raw_event
        except Exception as exc:
            yield _sse({"type": "error", "message": format_agent_stream_error(exc)})

    async def _stream_agent_response():
        if classify_agent_intent(payload.message, payload.selected_text) == "draft_key_memory":
            await create_memory_item(
                session,
                novel_id=novel_id,
                memory_type="key_memory",
                title=payload.message[:60] or "关键记忆",
                body=payload.message,
                importance=80,
                metadata={"source": "user_explicit"},
            )
            await session.commit()
            response = "已保存到记忆。"
            await append_message(session, conversation=conversation, role="assistant", content=response)
            yield _sse({"type": "delta", "content": response})
            yield _sse(
                {
                    "type": "done",
                    "message": response,
                    "context_status": ["已保存关键记忆。"],
                    "context_detail": None,
                    "conversation_id": str(conversation.id),
                    "confirmation": None,
                    "workspace_diff": None,
                    "workspace_nodes": None,
                }
            )
            return

        intent = classify_agent_intent(payload.message, payload.selected_text)
        if intent in {"organize_workspace", "cleanup_workspace"}:
            if intent == "cleanup_workspace":
                action_result = await cleanup_workspace_folders(
                    session, novel_id=novel_id, message=payload.message
                )
            else:
                action_result = await organize_workspace_tree(session, novel_id=novel_id)
            message = str(action_result.get("message", "操作已完成。"))
            workspace_diff = action_result.get("workspace_diff")
            workspace_nodes = await load_workspace_nodes(session, novel_id)
            await append_message(session, conversation=conversation, role="assistant", content=message)
            yield _sse({"type": "delta", "content": message})
            yield _sse(
                {
                    "type": "done",
                    "message": message,
                    "context_status": [],
                    "conversation_id": str(conversation.id),
                    "confirmation": None,
                    "workspace_diff": workspace_diff,
                    "workspace_nodes": [
                        WorkspaceNodeResponse.model_validate(node).model_dump(mode="json")
                        for node in workspace_nodes
                    ],
                }
            )
            return

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
            if not raw_event.startswith("data: "):
                yield raw_event
                continue

            event_payload: dict[str, Any] = json.loads(raw_event[6:].strip())
            if event_payload.get("type") == "done":
                final_message = str(event_payload.get("message", ""))
                if final_message:
                    await append_message(
                        session,
                        conversation=conversation,
                        role="assistant",
                        content=final_message,
                    )
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
                    event_payload["confirmation"] = ConfirmationResponse.model_validate(confirmation).model_dump(
                        mode="json"
                    )
                    event_payload.pop("proposed_payload", None)
                elif event_payload.get("confirmation_id"):
                    confirmation = await session.scalar(
                        select(PendingConfirmation).where(
                            PendingConfirmation.id == UUID(event_payload["confirmation_id"]),
                            PendingConfirmation.novel_id == novel_id,
                        )
                    )
                    if confirmation is not None:
                        event_payload["confirmation"] = ConfirmationResponse.model_validate(
                            confirmation
                        ).model_dump(mode="json")
                    event_payload.pop("confirmation_id", None)
                yield _sse(event_payload)
                continue

            yield raw_event

    return StreamingResponse(event_stream(), media_type="text/event-stream")
