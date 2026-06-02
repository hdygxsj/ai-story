from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Novel, User


async def get_owned_novel(session: AsyncSession, user: User, novel_id: UUID) -> Novel:
    novel = await session.scalar(select(Novel).where(Novel.id == novel_id, Novel.owner_id == user.id))
    if novel is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Novel not found")
    return novel
