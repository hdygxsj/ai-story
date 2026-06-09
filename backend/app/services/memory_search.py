from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryItem


async def search_memory_items(
    session: AsyncSession,
    *,
    novel_id: UUID,
    query: str,
    limit: int = 8,
) -> list[dict[str, str | int]]:
    items = list(
        await session.scalars(
            select(MemoryItem)
            .where(MemoryItem.novel_id == novel_id)
            .order_by(MemoryItem.importance.desc(), MemoryItem.created_at.desc())
        )
    )
    lowered = query.lower()
    ranked = [
        item
        for item in items
        if lowered in item.title.lower() or lowered in item.body.lower() or not lowered.strip()
    ]
    if not ranked:
        ranked = items
    return [
        {
            "id": str(item.id),
            "memory_type": item.memory_type,
            "title": item.title,
            "body": item.body,
            "importance": item.importance,
        }
        for item in ranked[:limit]
    ]
