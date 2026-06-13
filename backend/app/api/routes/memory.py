from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import MemoryItem, MemoryReviewItem, User
from app.schemas.memory import MemoryItemResponse, MemoryReviewCreate, MemoryReviewResponse
from app.services.memory import approve_review_item, create_memory_item, delete_memory_item
from app.services.novels import get_owned_novel
from app.services.rag import index_text

router = APIRouter(tags=["memory"])


@router.post(
    "/novels/{novel_id}/memory-review-items",
    response_model=MemoryReviewResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_memory_review_item(
    novel_id: UUID,
    payload: MemoryReviewCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryReviewItem:
    await get_owned_novel(session, current_user, novel_id)
    item = MemoryReviewItem(
        novel_id=novel_id,
        memory_type=payload.memory_type,
        title=payload.title,
        body=payload.body,
        importance=payload.importance,
        extra_metadata=payload.metadata,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item


@router.get("/novels/{novel_id}/memory-review-items", response_model=list[MemoryReviewResponse])
async def list_memory_review_items(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MemoryReviewItem]:
    await get_owned_novel(session, current_user, novel_id)
    items = await session.scalars(
        select(MemoryReviewItem)
        .where(MemoryReviewItem.novel_id == novel_id)
        .order_by(MemoryReviewItem.created_at, MemoryReviewItem.id)
    )
    return list(items)


@router.post("/memory-review-items/{item_id}/approve", response_model=MemoryItemResponse)
async def approve_memory_review_item(
    item_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryItem:
    review_item = await session.scalar(select(MemoryReviewItem).where(MemoryReviewItem.id == item_id))
    if review_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory review item not found",
        )
    await get_owned_novel(session, current_user, review_item.novel_id)
    memory = approve_review_item(review_item)
    session.add(memory)
    await session.flush()
    await index_text(
        session,
        novel_id=memory.novel_id,
        source_type="memory",
        source_id=str(memory.id),
        text=f"{memory.title}\n{memory.body}",
        metadata={"memory_type": memory.memory_type, "importance": memory.importance},
    )
    await session.commit()
    await session.refresh(memory)
    return memory


@router.post("/memory-review-items/{item_id}/reject", response_model=MemoryReviewResponse)
async def reject_memory_review_item(
    item_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryReviewItem:
    review_item = await session.scalar(select(MemoryReviewItem).where(MemoryReviewItem.id == item_id))
    if review_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory review item not found",
        )
    await get_owned_novel(session, current_user, review_item.novel_id)
    if review_item.status != "pending":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Memory review item already resolved")

    review_item.status = "rejected"
    await session.commit()
    await session.refresh(review_item)
    return review_item


@router.get("/novels/{novel_id}/memory-items", response_model=list[MemoryItemResponse])
async def list_memory_items(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MemoryItem]:
    await get_owned_novel(session, current_user, novel_id)
    items = await session.scalars(
        select(MemoryItem).where(MemoryItem.novel_id == novel_id).order_by(MemoryItem.created_at, MemoryItem.id)
    )
    return list(items)


@router.post(
    "/novels/{novel_id}/memory-items",
    response_model=MemoryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_formal_memory_item(
    novel_id: UUID,
    payload: MemoryReviewCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryItem:
    await get_owned_novel(session, current_user, novel_id)
    memory = await create_memory_item(
        session,
        novel_id=novel_id,
        memory_type=payload.memory_type,
        title=payload.title,
        body=payload.body,
        importance=payload.importance,
        metadata=payload.metadata,
    )
    await session.commit()
    await session.refresh(memory)
    return memory


@router.delete("/memory-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_formal_memory_item(
    item_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    deleted = await delete_memory_item(
        session,
        owner_id=current_user.id,
        item_id=item_id,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")

    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
