from copy import deepcopy
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.chapter_body import is_outline_or_meta_content
from app.models import Document, DocumentVersion, ModelProfile, Novel, PendingConfirmation, WorkspaceNode
from app.services.rag import extract_text_from_prosemirror, index_text
from app.services.workspace_actions import text_document


def mark_confirmation_resolved(confirmation: PendingConfirmation, status: str) -> None:
    confirmation.status = status
    confirmation.resolved_at = datetime.now(UTC)


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


def extract_document_plain_text(content: dict[str, Any]) -> str:
    paragraphs: list[str] = []

    def collect_text(node: Any) -> str:
        if isinstance(node, dict):
            text = node.get("text")
            parts = [text] if isinstance(text, str) else []
            for child in node.get("content", []):
                parts.append(collect_text(child))
            return "".join(parts)
        if isinstance(node, list):
            return "".join(collect_text(child) for child in node)
        return ""

    for block in content.get("content", []):
        paragraph = collect_text(block).strip()
        if paragraph:
            paragraphs.append(paragraph)
    if paragraphs:
        return "\n\n".join(paragraphs)
    return extract_text_from_prosemirror(content)


def confirmation_diff_texts(
    confirmation: PendingConfirmation,
    documents_by_id: dict[UUID, Document],
    versions_by_id: dict[UUID, DocumentVersion],
) -> tuple[str | None, str | None]:
    payload = confirmation.payload
    document_id_raw = payload.get("document_id")
    document = documents_by_id.get(UUID(str(document_id_raw))) if document_id_raw else None

    if confirmation.action_type == "document_update":
        before_text = extract_document_plain_text(document.content) if document else None
        content = payload.get("content")
        after_text = str(content) if isinstance(content, str) else None
        return before_text, after_text

    if confirmation.action_type in {"selection_replace", "rewrite_selection"}:
        selected_text = payload.get("selected_text")
        replacement_text = payload.get("replacement_text")
        if not isinstance(selected_text, str) or not isinstance(replacement_text, str):
            return None, None
        if document is None:
            return selected_text, replacement_text
        before_text = extract_document_plain_text(document.content)
        if selected_text not in before_text:
            return selected_text, replacement_text
        after_text = before_text.replace(selected_text, replacement_text, 1)
        return before_text, after_text

    if confirmation.action_type == "version_restore":
        version_id_raw = payload.get("version_id")
        if document is None or not version_id_raw:
            return None, None
        version = versions_by_id.get(UUID(str(version_id_raw)))
        if version is None:
            return extract_document_plain_text(document.content), None
        before_text = extract_document_plain_text(document.content)
        after_text = extract_document_plain_text(version.content)
        return before_text, after_text

    return None, None


def confirmation_is_stale(
    confirmation: PendingConfirmation,
    documents_by_id: dict[UUID, Document],
) -> bool:
    if confirmation.status != "pending":
        return False
    expected = confirmation.payload.get("expected_updated_at")
    document_id_raw = confirmation.payload.get("document_id")
    if not expected or not document_id_raw:
        return False
    document = documents_by_id.get(UUID(str(document_id_raw)))
    if document is None:
        return True
    return _timestamp_token(document.updated_at) != expected


def reject_pending_confirmations_for_document(
    confirmations: list[PendingConfirmation],
    *,
    document_id: UUID,
    exclude_confirmation_id: UUID | None = None,
) -> bool:
    document_id_str = str(document_id)
    changed = False
    for confirmation in confirmations:
        if confirmation.status != "pending":
            continue
        if exclude_confirmation_id is not None and confirmation.id == exclude_confirmation_id:
            continue
        if str(confirmation.payload.get("document_id", "")) != document_id_str:
            continue
        if not confirmation.payload.get("expected_updated_at"):
            continue
        mark_confirmation_resolved(confirmation, "rejected")
        changed = True
    return changed


async def expire_stale_pending_confirmations(
    session: AsyncSession,
    confirmations: list[PendingConfirmation],
) -> None:
    document_ids = {
        UUID(str(confirmation.payload["document_id"]))
        for confirmation in confirmations
        if confirmation.status == "pending"
        and confirmation.payload.get("document_id")
        and confirmation.payload.get("expected_updated_at")
    }
    documents_by_id: dict[UUID, Document] = {}
    if document_ids:
        documents = await session.scalars(select(Document).where(Document.id.in_(document_ids)))
        documents_by_id = {document.id: document for document in documents}

    changed = False
    for confirmation in confirmations:
        if confirmation.status == "pending" and confirmation_is_stale(confirmation, documents_by_id):
            mark_confirmation_resolved(confirmation, "rejected")
            changed = True
    if changed:
        await session.commit()


async def expire_pending_confirmations_for_document(
    session: AsyncSession,
    *,
    novel_id: UUID,
    document_id: UUID,
) -> None:
    confirmations = list(
        await session.scalars(
            select(PendingConfirmation).where(
                PendingConfirmation.novel_id == novel_id,
                PendingConfirmation.status == "pending",
            )
        )
    )
    if reject_pending_confirmations_for_document(confirmations, document_id=document_id):
        await session.commit()


async def build_confirmation_responses(
    session: AsyncSession,
    confirmations: list[PendingConfirmation],
    *,
    novel_id: UUID | None = None,
) -> list[dict[str, Any]]:
    document_ids = {
        UUID(str(confirmation.payload["document_id"]))
        for confirmation in confirmations
        if confirmation.payload.get("document_id")
    }
    documents_by_id: dict[UUID, Document] = {}
    if document_ids:
        documents = await session.scalars(select(Document).where(Document.id.in_(document_ids)))
        documents_by_id = {document.id: document for document in documents}

    chapter_titles_by_document_id: dict[UUID, str] = {}
    if novel_id and document_ids:
        nodes = await session.scalars(
            select(WorkspaceNode).where(
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.document_id.in_(document_ids),
            )
        )
        chapter_titles_by_document_id = {
            node.document_id: node.title for node in nodes if node.document_id is not None
        }

    version_ids = {
        UUID(str(confirmation.payload["version_id"]))
        for confirmation in confirmations
        if confirmation.action_type == "version_restore" and confirmation.payload.get("version_id")
    }
    versions_by_id: dict[UUID, DocumentVersion] = {}
    if version_ids:
        versions = await session.scalars(select(DocumentVersion).where(DocumentVersion.id.in_(version_ids)))
        versions_by_id = {version.id: version for version in versions}

    responses: list[dict[str, Any]] = []
    for confirmation in confirmations:
        document_id = confirmation.payload.get("document_id")
        document_uuid = UUID(str(document_id)) if document_id else None
        before_text, after_text = confirmation_diff_texts(confirmation, documents_by_id, versions_by_id)
        responses.append(
            {
                "id": confirmation.id,
                "action_type": confirmation.action_type,
                "status": confirmation.status,
                "payload": confirmation.payload,
                "document_id": document_uuid,
                "is_stale": False,
                "before_text": before_text,
                "after_text": after_text,
                "created_at": confirmation.created_at,
                "resolved_at": confirmation.resolved_at,
                "chapter_title": chapter_titles_by_document_id.get(document_uuid) if document_uuid else None,
            }
        )
    return responses


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
    if is_outline_or_meta_content(content):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="检测到爽点清单/大纲/要点列表，不能写入章节正文。请先生成小说散文正文。",
        )
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


async def restore_owned_document_version(
    session: AsyncSession,
    *,
    owner_id: UUID,
    novel_id: UUID,
    document_id: UUID,
    version_id: UUID,
    model_profile: ModelProfile | None = None,
) -> Document:
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

    session.add(
        DocumentVersion(document_id=document.id, source="user", content=deepcopy(document.content))
    )
    document.content = deepcopy(version.content)
    pending = list(
        await session.scalars(
            select(PendingConfirmation).where(
                PendingConfirmation.novel_id == novel_id,
                PendingConfirmation.status == "pending",
            )
        )
    )
    reject_pending_confirmations_for_document(pending, document_id=document.id)
    await index_text(
        session,
        novel_id=document.novel_id,
        source_type="document",
        source_id=str(document.id),
        text=extract_text_from_prosemirror(document.content),
        model_profile=model_profile,
    )
    await session.commit()
    await session.refresh(document)
    return document


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
        mark_confirmation_resolved(confirmation, "rejected")
        await session.commit()
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
    mark_confirmation_resolved(confirmation, "approved")
    pending = list(
        await session.scalars(
            select(PendingConfirmation).where(
                PendingConfirmation.novel_id == confirmation.novel_id,
                PendingConfirmation.status == "pending",
            )
        )
    )
    reject_pending_confirmations_for_document(
        pending,
        document_id=document.id,
        exclude_confirmation_id=confirmation.id,
    )
    await session.commit()
    return {"document_id": str(document.id), "confirmation_id": str(confirmation.id)}
