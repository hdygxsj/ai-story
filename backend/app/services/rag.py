import math
import re
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.model_runtime import embed_with_model_profile
from app.models import ModelProfile, Novel, RagChunk, WorkspaceNode

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


def embed_text_hash(text: str) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in re.findall(r"\w+", text.lower()):
        vector[hash(token) % EMBEDDING_DIMENSIONS] += 1.0
    length = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / length for value in vector]


async def embed_text(text: str, model_profile: ModelProfile | None = None) -> list[float]:
    if model_profile is not None:
        return await embed_with_model_profile(model_profile, text)
    return embed_text_hash(text)


async def get_embedding_model_profile(session: AsyncSession, novel: Novel) -> ModelProfile | None:
    if novel.default_model_profile_id is None:
        return None
    return await session.scalar(
        select(ModelProfile).where(
            ModelProfile.id == novel.default_model_profile_id,
            ModelProfile.owner_id == novel.owner_id,
        )
    )


def _similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


async def index_text(
    session: AsyncSession,
    *,
    novel_id: UUID,
    source_type: str,
    source_id: str,
    text: str,
    model_profile: ModelProfile | None = None,
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
            embedding=await embed_text(normalized, model_profile),
            extra_metadata=metadata or {},
        )
    )


async def search_rag_chunks(
    session: AsyncSession,
    *,
    novel_id: UUID,
    query: str,
    limit: int = 8,
    model_profile: ModelProfile | None = None,
    excluded_source_types: set[str] | None = None,
) -> list[RagChunk]:
    chunks = list(
        await session.scalars(select(RagChunk).where(RagChunk.novel_id == novel_id))
    )
    excluded = excluded_source_types or set()
    active_document_ids = {
        str(document_id)
        for document_id in await session.scalars(
            select(WorkspaceNode.document_id).where(
                WorkspaceNode.novel_id == novel_id,
                WorkspaceNode.status != "trashed",
                WorkspaceNode.document_id.is_not(None),
            )
        )
        if document_id is not None
    }
    chunks = [
        chunk
        for chunk in chunks
        if chunk.source_type not in excluded
        and (chunk.source_type != "document" or chunk.source_id in active_document_ids)
    ]
    query_embedding = await embed_text(query, model_profile)
    return sorted(
        chunks,
        key=lambda chunk: _similarity(query_embedding, chunk.embedding),
        reverse=True,
    )[:limit]
