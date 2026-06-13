from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryItem, MemoryReviewItem, Novel, RagChunk
from app.services.rag import index_text


async def create_memory_item(
    session: AsyncSession,
    *,
    novel_id: UUID,
    memory_type: str,
    title: str,
    body: str,
    importance: int = 50,
    metadata: dict[str, Any] | None = None,
) -> MemoryItem:
    memory = MemoryItem(
        novel_id=novel_id,
        memory_type=memory_type,
        title=title,
        body=body,
        importance=importance,
        extra_metadata=metadata or {},
    )
    session.add(memory)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="memory",
        source_id=str(memory.id),
        text=f"{title}\n{body}",
        metadata={
            **(metadata or {}),
            "memory_type": memory_type,
            "importance": importance,
        },
    )
    return memory


async def delete_memory_item(
    session: AsyncSession,
    *,
    owner_id: UUID,
    item_id: UUID,
) -> bool:
    memory = await session.scalar(
        select(MemoryItem)
        .join(Novel, Novel.id == MemoryItem.novel_id)
        .where(MemoryItem.id == item_id, Novel.owner_id == owner_id)
    )
    if memory is None:
        return False

    await session.execute(
        delete(RagChunk).where(
            RagChunk.novel_id == memory.novel_id,
            RagChunk.source_type == "memory",
            RagChunk.source_id == str(memory.id),
        )
    )
    await session.delete(memory)
    return True


def approve_review_item(review_item: MemoryReviewItem) -> MemoryItem:
    review_item.status = "approved"
    return MemoryItem(
        novel_id=review_item.novel_id,
        memory_type=review_item.memory_type,
        title=review_item.title,
        body=review_item.body,
        importance=review_item.importance,
        extra_metadata=review_item.extra_metadata,
    )
