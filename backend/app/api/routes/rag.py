from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import RagChunk, User
from app.schemas.rag import RagChunkResponse
from app.services.novels import get_owned_novel
from app.services.rag import get_embedding_model_profile, search_rag_chunks

router = APIRouter(tags=["rag"])


@router.get("/novels/{novel_id}/rag/search", response_model=list[RagChunkResponse])
async def search_rag(
    novel_id: UUID,
    query: Annotated[str, Query(min_length=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 8,
) -> list[RagChunk]:
    novel = await get_owned_novel(session, current_user, novel_id)
    return await search_rag_chunks(
        session,
        novel_id=novel_id,
        query=query,
        limit=limit,
        model_profile=await get_embedding_model_profile(session, novel),
    )
