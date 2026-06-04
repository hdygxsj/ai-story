import re
from typing import Annotated, Any
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Document, DocumentVersion, ModelProfile, Novel, User, WorkspaceNode
from app.schemas.document import DocumentResponse, DocumentUpdate, DocumentVersionResponse
from app.schemas.novel import NovelCreate, NovelImport, NovelResponse, NovelUpdate
from app.schemas.workspace import (
    WorkspaceNodeCreate,
    WorkspaceNodeReorderRequest,
    WorkspaceNodeResponse,
    WorkspaceNodeUpdate,
)
from app.services.novels import get_owned_novel
from app.services.rag import extract_text_from_prosemirror, get_embedding_model_profile, index_text

router = APIRouter(tags=["novels"])


def _text_to_document(text: str) -> dict[str, Any]:
    paragraphs = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": paragraph}]}
            for paragraph in paragraphs
        ],
    }


def _split_imported_chapters(content: str, format_name: str) -> list[tuple[str, str]]:
    if format_name == "markdown":
        matches = list(re.finditer(r"(?m)^#{1,3}\s+(.+?)\s*$", content))
        if matches:
            chapters: list[tuple[str, str]] = []
            for index, match in enumerate(matches):
                start = match.end()
                end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
                chapters.append((match.group(1).strip(), content[start:end].strip()))
            return chapters

    pattern = re.compile(r"(?m)^(第[^\n]{1,40}[章节卷部].*?)$")
    matches = list(pattern.finditer(content))
    if matches:
        chapters = []
        for index, match in enumerate(matches):
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
            chapters.append((match.group(1).strip(), content[start:end].strip()))
        return chapters

    return [("第一章", content.strip())]


@router.post("/novels", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
async def create_novel(
    payload: NovelCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Novel:
    novel = Novel(
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
    )
    session.add(novel)
    await session.commit()
    await session.refresh(novel)
    return novel


@router.post("/novels/import", response_model=NovelResponse, status_code=status.HTTP_201_CREATED)
async def import_novel(
    payload: NovelImport,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Novel:
    novel = Novel(
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
    )
    session.add(novel)
    await session.flush()

    for position, (title, body) in enumerate(_split_imported_chapters(payload.content, payload.format)):
        document = Document(novel_id=novel.id, content=_text_to_document(body))
        session.add(document)
        await session.flush()
        session.add(
            WorkspaceNode(
                novel_id=novel.id,
                document_id=document.id,
                title=title[:200],
                node_type="chapter",
                position=position,
            )
        )
        await index_text(
            session,
            novel_id=novel.id,
            source_type="document",
            source_id=str(document.id),
            text=extract_text_from_prosemirror(document.content),
        )

    await session.commit()
    await session.refresh(novel)
    return novel


@router.get("/novels", response_model=list[NovelResponse])
async def list_novels(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Novel]:
    novels = await session.scalars(
        select(Novel).where(Novel.owner_id == current_user.id).order_by(Novel.created_at, Novel.id)
    )
    return list(novels)


@router.patch("/novels/{novel_id}", response_model=NovelResponse)
async def update_novel(
    novel_id: UUID,
    payload: NovelUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Novel:
    novel = await get_owned_novel(session, current_user, novel_id)
    if payload.default_model_profile_id is not None:
        model_profile = await session.scalar(
            select(ModelProfile).where(
                ModelProfile.id == payload.default_model_profile_id,
                ModelProfile.owner_id == current_user.id,
            )
        )
        if model_profile is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model profile not found")
    novel.default_model_profile_id = payload.default_model_profile_id
    await session.commit()
    await session.refresh(novel)
    return novel


@router.get("/novels/{novel_id}/export")
async def export_novel(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    export_format: str = Query("txt", alias="format"),
) -> Response:
    novel = await get_owned_novel(session, current_user, novel_id)
    if export_format not in {"markdown", "txt"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format")

    nodes = list(
        await session.scalars(
            select(WorkspaceNode)
            .where(
                WorkspaceNode.novel_id == novel.id,
                WorkspaceNode.node_type != "folder",
            )
            .order_by(WorkspaceNode.position, WorkspaceNode.created_at, WorkspaceNode.id)
        )
    )
    document_ids = [node.document_id for node in nodes if node.document_id is not None]
    documents = {
        document.id: document
        for document in await session.scalars(select(Document).where(Document.id.in_(document_ids)))
    }

    sections: list[str] = []
    for node in nodes:
        document = documents.get(node.document_id)
        body = extract_text_from_prosemirror(document.content) if document else ""
        prefix = f"# {node.title}" if export_format == "markdown" else node.title
        sections.append(f"{prefix}\n\n{body}".strip())

    media_type = "text/markdown; charset=utf-8" if export_format == "markdown" else "text/plain; charset=utf-8"
    filename = quote(f"{novel.title}.{'md' if export_format == 'markdown' else 'txt'}")
    return Response(
        "\n\n".join(sections),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"},
    )


@router.post(
    "/novels/{novel_id}/nodes",
    response_model=WorkspaceNodeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_node(
    novel_id: UUID,
    payload: WorkspaceNodeCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceNode:
    novel = await get_owned_novel(session, current_user, novel_id)
    if payload.parent_id is not None:
        parent = await session.scalar(
            select(WorkspaceNode).where(
                WorkspaceNode.id == payload.parent_id,
                WorkspaceNode.novel_id == novel.id,
                WorkspaceNode.node_type == "folder",
            )
        )
        if parent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")

    document_id = None
    if payload.node_type != "folder":
        document = Document(novel_id=novel.id)
        session.add(document)
        await session.flush()
        document_id = document.id

    siblings = list(
        await session.scalars(
            select(WorkspaceNode).where(
                WorkspaceNode.novel_id == novel.id,
                WorkspaceNode.parent_id == payload.parent_id,
            )
        )
    )
    node = WorkspaceNode(
        novel_id=novel.id,
        parent_id=payload.parent_id,
        document_id=document_id,
        title=payload.title,
        node_type=payload.node_type,
        position=(max((sibling.position for sibling in siblings), default=-1) + 1),
    )
    session.add(node)
    await session.commit()
    await session.refresh(node)
    return node


@router.get("/novels/{novel_id}/nodes", response_model=list[WorkspaceNodeResponse])
async def list_nodes(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WorkspaceNode]:
    await get_owned_novel(session, current_user, novel_id)
    nodes = await session.scalars(
        select(WorkspaceNode)
        .where(WorkspaceNode.novel_id == novel_id)
        .order_by(WorkspaceNode.position, WorkspaceNode.created_at)
    )
    return list(nodes)


def _assert_no_workspace_cycles(nodes: dict[UUID, WorkspaceNode], parent_by_id: dict[UUID, UUID | None]) -> None:
    for node_id in parent_by_id:
        seen: set[UUID] = set()
        parent_id = parent_by_id.get(node_id)
        while parent_id is not None:
            if parent_id == node_id or parent_id in seen:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Workspace node cycle detected")
            seen.add(parent_id)
            parent_id = parent_by_id.get(parent_id, nodes[parent_id].parent_id if parent_id in nodes else None)


def _sort_workspace_nodes(nodes: list[WorkspaceNode]) -> list[WorkspaceNode]:
    return sorted(
        nodes,
        key=lambda node: (
            "" if node.parent_id is None else str(node.parent_id),
            node.position,
            node.created_at,
            str(node.id),
        ),
    )


def _normalize_workspace_positions(
    nodes: dict[UUID, WorkspaceNode],
    parent_ids: set[UUID | None],
    priority_by_id: dict[UUID, int] | None = None,
) -> None:
    priority_by_id = priority_by_id or {}
    for parent_id in parent_ids:
        siblings = [node for node in nodes.values() if node.parent_id == parent_id]
        siblings.sort(
            key=lambda node: (
                node.position,
                0 if node.id in priority_by_id else 1,
                priority_by_id.get(node.id, 0),
                node.created_at,
                str(node.id),
            )
        )
        for position, node in enumerate(siblings):
            node.position = position


@router.patch("/novels/{novel_id}/nodes/reorder", response_model=list[WorkspaceNodeResponse])
async def reorder_nodes(
    novel_id: UUID,
    payload: WorkspaceNodeReorderRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[WorkspaceNode]:
    novel = await get_owned_novel(session, current_user, novel_id)
    nodes = {
        node.id: node
        for node in await session.scalars(select(WorkspaceNode).where(WorkspaceNode.novel_id == novel.id))
    }
    requested_ids = {item.id for item in payload.items}
    if missing_ids := requested_ids - set(nodes):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workspace node not found: {next(iter(missing_ids))}",
        )

    parent_by_id = {node_id: node.parent_id for node_id, node in nodes.items()}
    affected_parent_ids: set[UUID | None] = set()
    for item in payload.items:
        affected_parent_ids.add(nodes[item.id].parent_id)
        affected_parent_ids.add(item.parent_id)
        parent_by_id[item.id] = item.parent_id
        if item.parent_id is not None:
            parent = nodes.get(item.parent_id)
            if parent is None or parent.node_type != "folder":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")
            if item.parent_id == item.id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node cannot parent itself")

    _assert_no_workspace_cycles(nodes, parent_by_id)

    for item in payload.items:
        node = nodes[item.id]
        node.parent_id = item.parent_id
        node.position = item.position
        if item.title is not None:
            node.title = item.title
        if item.status is not None:
            node.status = item.status

    _normalize_workspace_positions(
        nodes,
        affected_parent_ids,
        priority_by_id={item.id: index for index, item in enumerate(payload.items)},
    )

    await session.commit()
    updated_nodes = list(
        await session.scalars(
            select(WorkspaceNode)
            .where(WorkspaceNode.novel_id == novel.id)
            .order_by(WorkspaceNode.position, WorkspaceNode.created_at)
        )
    )
    return _sort_workspace_nodes(updated_nodes)


@router.patch("/novels/{novel_id}/nodes/{node_id}", response_model=WorkspaceNodeResponse)
async def update_node(
    novel_id: UUID,
    node_id: UUID,
    payload: WorkspaceNodeUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> WorkspaceNode:
    novel = await get_owned_novel(session, current_user, novel_id)
    node = await session.scalar(
        select(WorkspaceNode).where(
            WorkspaceNode.id == node_id,
            WorkspaceNode.novel_id == novel.id,
        )
    )
    if node is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Node not found")

    all_nodes = {
        item.id: item
        for item in await session.scalars(select(WorkspaceNode).where(WorkspaceNode.novel_id == novel.id))
    }
    old_parent_id = node.parent_id
    if payload.parent_id is not None:
        if payload.parent_id == node.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Node cannot parent itself")
        parent = await session.scalar(
            select(WorkspaceNode).where(
                WorkspaceNode.id == payload.parent_id,
                WorkspaceNode.novel_id == novel.id,
                WorkspaceNode.node_type == "folder",
            )
        )
        if parent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent folder not found")
        node.parent_id = payload.parent_id
    elif "parent_id" in payload.model_fields_set:
        node.parent_id = None

    if payload.title is not None:
        node.title = payload.title
    if payload.position is not None:
        node.position = payload.position

    _assert_no_workspace_cycles(all_nodes, {item_id: item.parent_id for item_id, item in all_nodes.items()})
    _normalize_workspace_positions(
        all_nodes,
        {old_parent_id, node.parent_id},
        priority_by_id={node.id: 0} if payload.position is not None or old_parent_id != node.parent_id else {},
    )

    await session.commit()
    await session.refresh(node)
    return node


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Document:
    document = await session.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    novel = await get_owned_novel(session, current_user, document.novel_id)
    return document


@router.patch("/documents/{document_id}", response_model=DocumentResponse)
async def update_document(
    document_id: UUID,
    payload: DocumentUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Document:
    document = await session.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    novel = await get_owned_novel(session, current_user, document.novel_id)

    version = DocumentVersion(document_id=document.id, source="user", content=document.content)
    session.add(version)
    document.content = payload.content
    await index_text(
        session,
        novel_id=document.novel_id,
        source_type="document",
        source_id=str(document.id),
        text=extract_text_from_prosemirror(payload.content),
        model_profile=await get_embedding_model_profile(session, novel),
    )
    await session.commit()
    await session.refresh(document)
    return document


@router.get("/documents/{document_id}/versions", response_model=list[DocumentVersionResponse])
async def list_document_versions(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[DocumentVersion]:
    document = await session.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await get_owned_novel(session, current_user, document.novel_id)
    versions = await session.scalars(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document.id)
        .order_by(DocumentVersion.created_at, DocumentVersion.id)
    )
    return list(versions)
