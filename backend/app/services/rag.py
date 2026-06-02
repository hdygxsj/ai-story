import math
import re
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import RagChunk

EMBEDDING_DIMENSIONS = 64


def extract_text_from_prosemirror(content: dict[str, Any]) -> str:
    parts: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            text = node.get("text")
            if isinstance(text, str):
                parts.append(text)
            for child in node.get("content", []):
                visit(child)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(content)
    return " ".join(part.strip() for part in parts if part.strip())


def embed_text(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in re.findall(r"\w+", text.lower()):
        vector[hash(token) % EMBEDDING_DIMENSIONS] += 1.0
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / length for value in vector]


def _similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


async def index_text(
    session: AsyncSession,
    *,
    novel_id: UUID,
    source_type: str,
    source_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    normalized = text.strip()
    await session.execute(
        delete(RagChunk).where(
            RagChunk.novel_id == novel_id,
            RagChunk.source_type == source_type,
            RagChunk.source_id == source_id,
        )
    )
    if not normalized:
        return
    session.add(
        RagChunk(
            novel_id=novel_id,
            source_type=source_type,
            source_id=source_id,
            text=normalized,
            embedding=embed_text(normalized),
            extra_metadata=metadata or {},
        )
    )


async def search_rag_chunks(
    session: AsyncSession,
    *,
    novel_id: UUID,
    query: str,
    limit: int = 8,
) -> list[RagChunk]:
    chunks = list(
        await session.scalars(select(RagChunk).where(RagChunk.novel_id == novel_id))
    )
    query_embedding = embed_text(query)
    return sorted(
        chunks,
        key=lambda chunk: _similarity(query_embedding, chunk.embedding),
        reverse=True,
    )[:limit]
