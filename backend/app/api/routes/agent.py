import json
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chat_stream import _sse, stream_agent_events
from app.agent.runtime import invoke_agent_graph
from app.agent.tools import classify_agent_intent
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Document, MemoryReviewItem, ModelProfile, PendingConfirmation, User, WorkspaceNode
from app.schemas.agent import AgentMessageRequest, AgentMessageResponse
from app.schemas.confirmation import ConfirmationResponse
from app.schemas.workspace import WorkspaceNodeResponse
from app.services.conversations import append_message, resolve_conversation_for_message
from app.services.novels import get_owned_novel

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


def _workspace_snapshot(nodes: list[WorkspaceNode]) -> list[dict[str, object]]:
    return [
        {
            "id": str(node.id),
            "title": node.title,
            "parent_id": str(node.parent_id) if node.parent_id else None,
            "position": node.position,
            "status": node.status,
        }
        for node in nodes
    ]


def _is_draft_like_node(node: WorkspaceNode) -> bool:
    return node.node_type != "folder" and (
        node.node_type == "draft" or "草稿" in node.title or "废稿" in node.title
    )


async def _organize_workspace_tree(
    novel_id: UUID,
    session: AsyncSession,
) -> tuple[str, dict[str, object] | None, list[WorkspaceNode]]:
    nodes = list(
        await session.scalars(
            select(WorkspaceNode)
            .where(WorkspaceNode.novel_id == novel_id)
            .order_by(WorkspaceNode.position, WorkspaceNode.created_at)
        )
    )
    before = _workspace_snapshot(nodes)
    root_folders = [node for node in nodes if node.parent_id is None and node.node_type == "folder"]
    drafts_folder = next((node for node in root_folders if node.title in {"草稿", "草稿箱", "废稿箱"}), None)
    draft_nodes = [node for node in nodes if _is_draft_like_node(node)]

    if drafts_folder is None and draft_nodes:
        root_positions = [node.position for node in nodes if node.parent_id is None]
        drafts_folder = WorkspaceNode(
            novel_id=novel_id,
            title="草稿",
            node_type="folder",
            position=(max(root_positions) + 1) if root_positions else 0,
        )
        session.add(drafts_folder)
        await session.flush()
        nodes.append(drafts_folder)

    changes: list[dict[str, object]] = []
    if drafts_folder is not None:
        existing_child_positions = [
            node.position for node in nodes if node.parent_id == drafts_folder.id and node.id != drafts_folder.id
        ]
        next_position = (max(existing_child_positions) + 1) if existing_child_positions else 0
        for node in draft_nodes:
            if node.parent_id == drafts_folder.id:
                continue
            changes.append(
                {
                    "action": "move",
                    "node_id": str(node.id),
                    "title": node.title,
                    "before_parent_id": str(node.parent_id) if node.parent_id else None,
                    "after_parent_id": str(drafts_folder.id),
                    "before_position": node.position,
                    "after_position": next_position,
                }
            )
            node.parent_id = drafts_folder.id
            node.position = next_position
            next_position += 1

    if not changes:
        return "没有发现需要整理的章节或草稿。", None, nodes

    await session.commit()
    updated_nodes = list(
        await session.scalars(
            select(WorkspaceNode)
            .where(WorkspaceNode.novel_id == novel_id)
            .order_by(WorkspaceNode.position, WorkspaceNode.created_at)
        )
    )
    after = _workspace_snapshot(updated_nodes)
    diff = {
        "summary": "Agent 已整理章节目录",
        "before": before,
        "after": after,
        "changes": changes,
    }
    return "已整理章节、文件夹和草稿，并保存目录草稿。", diff, updated_nodes


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

    if classify_agent_intent(payload.message, payload.selected_text) == "organize_workspace":
        message, workspace_diff, workspace_nodes = await _organize_workspace_tree(novel_id, session)
        await append_message(session, conversation=conversation, role="assistant", content=message)
        return AgentMessageResponse(
            message=message,
            context_status=[],
            conversation_id=conversation.id,
            confirmation=None,
            workspace_diff=workspace_diff,
            workspace_nodes=workspace_nodes,
        )

    result = await invoke_agent_graph(
        session,
        state={
            "novel_id": novel_id,
            "document_id": payload.document_id,
            "message": payload.message,
            "model_profile": model_profile,
            "selected_text": payload.selected_text,
        },
        model_profile=model_profile,
        conversation_id=conversation.id,
    )

    confirmation = None
    if result.get("proposed_payload"):
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
    return AgentMessageResponse(
        message=result["response"],
        context_status=result["context_status"],
        conversation_id=conversation.id,
        confirmation=confirmation,
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
        if classify_agent_intent(payload.message, payload.selected_text) == "draft_key_memory":
            review_item = MemoryReviewItem(
                novel_id=novel_id,
                memory_type="key_memory",
                title=payload.message[:60] or "关键记忆",
                body=payload.message,
                importance=80,
            )
            session.add(review_item)
            await session.commit()
            response = "已提交关键记忆，请在记忆页审核。"
            await append_message(session, conversation=conversation, role="assistant", content=response)
            yield _sse({"type": "delta", "content": response})
            yield _sse(
                {
                    "type": "done",
                    "message": response,
                    "context_status": ["已创建记忆审核项。"],
                    "context_detail": None,
                    "conversation_id": str(conversation.id),
                    "confirmation": None,
                    "workspace_diff": None,
                    "workspace_nodes": None,
                }
            )
            return

        if classify_agent_intent(payload.message, payload.selected_text) == "organize_workspace":
            message, workspace_diff, workspace_nodes = await _organize_workspace_tree(novel_id, session)
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
                yield _sse(event_payload)
                continue

            yield raw_event

    return StreamingResponse(event_stream(), media_type="text/event-stream")
