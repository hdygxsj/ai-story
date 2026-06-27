from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Document, DocumentVersion, PendingConfirmation, User
from app.schemas.confirmation import ConfirmationResponse
from app.services.novels import get_owned_novel
from app.services.document_actions import (
    approve_document_confirmation,
    build_confirmation_responses,
    mark_confirmation_resolved,
)
from app.services.rag import extract_text_from_prosemirror, index_text

router = APIRouter(tags=["confirmations"])


@router.get("/novels/{novel_id}/confirmations", response_model=list[ConfirmationResponse])
async def list_confirmations(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ConfirmationResponse]:
    await get_owned_novel(session, current_user, novel_id)
    confirmations = list(
        await session.scalars(
        select(PendingConfirmation)
        .where(
            PendingConfirmation.novel_id == novel_id,
            PendingConfirmation.status == "pending",
        )
        .order_by(PendingConfirmation.created_at, PendingConfirmation.id)
        )
    )
    active_confirmations = [confirmation for confirmation in confirmations if confirmation.status == "pending"]
    return await build_confirmation_responses(session, active_confirmations, novel_id=novel_id)


@router.get("/novels/{novel_id}/confirmations/history", response_model=list[ConfirmationResponse])
async def list_confirmation_history(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ConfirmationResponse]:
    await get_owned_novel(session, current_user, novel_id)
    confirmations = list(
        await session.scalars(
            select(PendingConfirmation)
            .where(
                PendingConfirmation.novel_id == novel_id,
                PendingConfirmation.status.in_(("approved", "rejected")),
            )
            .order_by(PendingConfirmation.resolved_at.desc(), PendingConfirmation.created_at.desc(), PendingConfirmation.id.desc())
        )
    )
    return await build_confirmation_responses(session, confirmations, novel_id=novel_id)


@router.post("/confirmations/{confirmation_id}/approve", response_model=ConfirmationResponse)
async def approve_confirmation(
    confirmation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict:
    confirmation = await session.scalar(
        select(PendingConfirmation).where(PendingConfirmation.id == confirmation_id)
    )
    if confirmation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmation not found")
    await get_owned_novel(session, current_user, confirmation.novel_id)
    if confirmation.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Confirmation already resolved")

    document_id = None
    if confirmation.action_type in {"document_update", "selection_replace", "version_restore"} or (
        confirmation.action_type == "rewrite_selection"
        and confirmation.payload.get("expected_updated_at") is not None
    ):
        result = await approve_document_confirmation(
            session,
            owner_id=current_user.id,
            confirmation=confirmation,
        )
        document_id = UUID(result["document_id"])
        await session.refresh(confirmation)
    elif confirmation.action_type == "rewrite_selection":
        document = await session.scalar(
            select(Document).where(
                Document.id == UUID(confirmation.payload["document_id"]),
                Document.novel_id == confirmation.novel_id,
            )
        )
        if document is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
        session.add(DocumentVersion(document_id=document.id, source="agent", content=document.content))
        document.content = {
            "type": "doc",
            "content": [{"type": "paragraph", "text": confirmation.payload["replacement_text"]}],
        }
        await index_text(
            session,
            novel_id=document.novel_id,
            source_type="document",
            source_id=str(document.id),
            text=extract_text_from_prosemirror(document.content),
        )

        mark_confirmation_resolved(confirmation, "approved")
        await session.commit()
        await session.refresh(confirmation)
        document_id = document.id
    else:
        mark_confirmation_resolved(confirmation, "approved")
        await session.commit()
        await session.refresh(confirmation)
    responses = await build_confirmation_responses(session, [confirmation], novel_id=confirmation.novel_id)
    response = responses[0]
    response["document_id"] = document_id
    return response


@router.post("/confirmations/{confirmation_id}/reject", response_model=ConfirmationResponse)
async def reject_confirmation(
    confirmation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConfirmationResponse:
    confirmation = await session.scalar(
        select(PendingConfirmation).where(PendingConfirmation.id == confirmation_id)
    )
    if confirmation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Confirmation not found")
    await get_owned_novel(session, current_user, confirmation.novel_id)
    if confirmation.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Confirmation already resolved")

    mark_confirmation_resolved(confirmation, "rejected")
    await session.commit()
    await session.refresh(confirmation)
    responses = await build_confirmation_responses(session, [confirmation], novel_id=confirmation.novel_id)
    return responses[0]
