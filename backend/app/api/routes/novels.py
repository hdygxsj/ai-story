from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import Document, DocumentVersion, Novel, User, WorkspaceNode
from app.schemas.document import DocumentResponse, DocumentUpdate, DocumentVersionResponse
from app.schemas.novel import NovelCreate, NovelResponse
from app.schemas.workspace import WorkspaceNodeCreate, WorkspaceNodeResponse
from app.services.novels import get_owned_novel
from app.services.rag import extract_text_from_prosemirror, index_text

router = APIRouter(tags=["novels"])


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


@router.get("/novels", response_model=list[NovelResponse])
async def list_novels(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[Novel]:
    novels = await session.scalars(
        select(Novel).where(Novel.owner_id == current_user.id).order_by(Novel.created_at, Novel.id)
    )
    return list(novels)


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
            )
        )
        if parent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent not found")

    document_id = None
    if payload.node_type != "folder":
        document = Document(novel_id=novel.id)
        session.add(document)
        await session.flush()
        document_id = document.id

    node = WorkspaceNode(
        novel_id=novel.id,
        parent_id=payload.parent_id,
        document_id=document_id,
        title=payload.title,
        node_type=payload.node_type,
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


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Document:
    document = await session.scalar(select(Document).where(Document.id == document_id))
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    await get_owned_novel(session, current_user, document.novel_id)
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
    await get_owned_novel(session, current_user, document.novel_id)

    version = DocumentVersion(document_id=document.id, source="user", content=document.content)
    session.add(version)
    document.content = payload.content
    await index_text(
        session,
        novel_id=document.novel_id,
        source_type="document",
        source_id=str(document.id),
        text=extract_text_from_prosemirror(payload.content),
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
