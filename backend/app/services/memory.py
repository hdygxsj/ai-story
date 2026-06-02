from app.models import MemoryItem, MemoryReviewItem


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
