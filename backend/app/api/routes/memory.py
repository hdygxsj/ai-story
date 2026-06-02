from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import MemoryItem, MemoryReviewItem, User
from app.schemas.memory import MemoryItemResponse, MemoryReviewCreate, MemoryReviewResponse
from app.services.memory import approve_review_item
from app.services.novels import get_owned_novel

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
    await session.commit()
    await session.refresh(memory)
    return memory
