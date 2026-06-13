from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Document, DocumentVersion, Novel, PendingConfirmation
from app.services.rag import extract_text_from_prosemirror, index_text
from app.services.workspace_actions import text_document


async def get_owned_document(
    session: AsyncSession,
    *,
    owner_id: UUID,
    novel_id: UUID,
    document_id: UUID,
) -> Document:
    document = await session.scalar(
        select(Document)
        .join(Novel, Novel.id == Document.novel_id)
        .where(
            Document.id == document_id,
            Document.novel_id == novel_id,
            Novel.owner_id == owner_id,
        )
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return document


def _timestamp_token(value: datetime) -> str:
    if value.tzinfo is not None:
        value = value.astimezone(UTC).replace(tzinfo=None)
    return value.isoformat(timespec="microseconds")


def _proposal_payload(document: Document, **values: Any) -> dict[str, Any]:
    return {
        "document_id": str(document.id),
        "expected_updated_at": _timestamp_token(document.updated_at),
        **values,
    }


async def _create_proposal(
    session: AsyncSession,
    *,
    document: Document,
    action_type: str,
    payload: dict[str, Any],
) -> PendingConfirmation:
    confirmation = PendingConfirmation(
        novel_id=document.novel_id,
        action_type=action_type,
        payload=payload,
    )
    session.add(confirmation)
    await session.commit()
    await session.refresh(confirmation)
    return confirmation


async def create_document_update_proposal(
    session: AsyncSession,
    *,
    owner_id: UUID,
    novel_id: UUID,
    document_id: UUID,
    content: str,
) -> PendingConfirmation:
    document = await get_owned_document(
        session, owner_id=owner_id, novel_id=novel_id, document_id=document_id
    )
    if not content.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Content is empty")
    return await _create_proposal(
        session,
        document=document,
        action_type="document_update",
        payload=_proposal_payload(document, content=content),
    )


async def create_selection_replace_proposal(
    session: AsyncSession,
    *,
    owner_id: UUID,
    novel_id: UUID,
    document_id: UUID,
    selected_text: str,
    replacement_text: str,
    action_type: str = "selection_replace",
) -> PendingConfirmation:
    document = await get_owned_document(
        session, owner_id=owner_id, novel_id=novel_id, document_id=document_id
    )
    if not selected_text:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Selected text is empty",
        )
    return await _create_proposal(
        session,
        document=document,
        action_type=action_type,
        payload=_proposal_payload(
            document,
            selected_text=selected_text,
            replacement_text=replacement_text,
        ),
    )


async def list_owned_document_versions(
    session: AsyncSession,
    *,
    owner_id: UUID,
    novel_id: UUID,
    document_id: UUID,
) -> list[DocumentVersion]:
    await get_owned_document(
        session, owner_id=owner_id, novel_id=novel_id, document_id=document_id
    )
    return list(
        await session.scalars(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == document_id)
            .order_by(DocumentVersion.created_at.desc(), DocumentVersion.id.desc())
        )
    )


async def create_version_restore_proposal(
    session: AsyncSession,
    *,
    owner_id: UUID,
    novel_id: UUID,
    document_id: UUID,
    version_id: UUID,
) -> PendingConfirmation:
    document = await get_owned_document(
        session, owner_id=owner_id, novel_id=novel_id, document_id=document_id
    )
    version = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document.id,
        )
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found")
    return await _create_proposal(
        session,
        document=document,
        action_type="version_restore",
        payload=_proposal_payload(document, version_id=str(version.id)),
    )


def _replace_unique_text_node(content: dict[str, Any], selected_text: str, replacement_text: str) -> dict[str, Any]:
    updated = deepcopy(content)
    matches: list[dict[str, Any]] = []

    def visit(value: Any) -> None:
        if isinstance(value, list):
            for item in value:
                visit(item)
            return
        if not isinstance(value, dict):
            return
        text = value.get("text")
        if isinstance(text, str) and selected_text in text:
            matches.append(value)
        visit(value.get("content"))

    visit(updated)
    if len(matches) != 1 or matches[0]["text"].count(selected_text) != 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Selected text no longer has a unique editable match",
        )
    matches[0]["text"] = matches[0]["text"].replace(selected_text, replacement_text, 1)
    return updated


async def approve_document_confirmation(
    session: AsyncSession,
    *,
    owner_id: UUID,
    confirmation: PendingConfirmation,
) -> dict[str, str]:
    if confirmation.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Confirmation already resolved")
    if confirmation.action_type not in {
        "document_update",
        "selection_replace",
        "rewrite_selection",
        "version_restore",
    }:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unsupported action")

    document = await get_owned_document(
        session,
        owner_id=owner_id,
        novel_id=confirmation.novel_id,
        document_id=UUID(confirmation.payload["document_id"]),
    )
    if _timestamp_token(document.updated_at) != confirmation.payload.get("expected_updated_at"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document changed after this proposal was created",
        )

    if confirmation.action_type == "document_update":
        next_content = text_document(str(confirmation.payload["content"]))
    elif confirmation.action_type in {"selection_replace", "rewrite_selection"}:
        next_content = _replace_unique_text_node(
            document.content,
            str(confirmation.payload["selected_text"]),
            str(confirmation.payload["replacement_text"]),
        )
    else:
        version = await session.scalar(
            select(DocumentVersion).where(
                DocumentVersion.id == UUID(confirmation.payload["version_id"]),
                DocumentVersion.document_id == document.id,
            )
        )
        if version is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document version not found")
        next_content = deepcopy(version.content)

    session.add(DocumentVersion(document_id=document.id, source="agent", content=deepcopy(document.content)))
    document.content = next_content
    await index_text(
        session,
        novel_id=document.novel_id,
        source_type="document",
        source_id=str(document.id),
        text=extract_text_from_prosemirror(document.content),
    )
    confirmation.status = "approved"
    await session.commit()
    return {"document_id": str(document.id), "confirmation_id": str(confirmation.id)}
