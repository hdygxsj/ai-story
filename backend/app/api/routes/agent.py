from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.model_runtime import build_chat_model
from app.agent.graph import build_agent_graph
from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Document, ModelProfile, PendingConfirmation, User
from app.schemas.agent import AgentMessageRequest, AgentMessageResponse
from app.services.novels import get_owned_novel

router = APIRouter(prefix="/novels/{novel_id}/agent", tags=["agent"])


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

    if novel.default_model_profile_id is not None:
        model_profile = await session.scalar(
            select(ModelProfile).where(
                ModelProfile.id == novel.default_model_profile_id,
                ModelProfile.owner_id == current_user.id,
            )
        )
        if model_profile is not None:
            build_chat_model(model_profile, purpose="chat")

    graph = build_agent_graph()
    result = graph.invoke(
        {
            "novel_id": novel_id,
            "document_id": payload.document_id,
            "message": payload.message,
            "selected_text": payload.selected_text,
        }
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

    return AgentMessageResponse(
        message=result["response"],
        context_status=result["context_status"],
        confirmation=confirmation,
    )


@router.post("/messages/stream")
async def stream_agent_message(
    novel_id: UUID,
    payload: AgentMessageRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> StreamingResponse:
    await get_owned_novel(session, current_user, novel_id)

    graph = build_agent_graph()
    result = graph.invoke(
        {
            "novel_id": novel_id,
            "document_id": payload.document_id,
            "message": payload.message,
            "selected_text": payload.selected_text,
        }
    )

    async def event_stream():
        yield f"data: {result['response']}\n\n"
        for chunk in result["response"].split(" "):
            yield f"data: {chunk} \n\n"
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
