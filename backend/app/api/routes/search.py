from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.search import DocumentSearchHitResponse
from app.services.document_search import search_novel_documents
from app.services.novels import get_owned_novel

router = APIRouter(tags=["search"])


@router.get("/novels/{novel_id}/search", response_model=list[DocumentSearchHitResponse])
async def search_novel(
    novel_id: UUID,
    query: Annotated[str, Query(min_length=1)],
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    limit: int = 50,
) -> list[DocumentSearchHitResponse]:
    await get_owned_novel(session, current_user, novel_id)
    results = await search_novel_documents(
        session,
        novel_id=novel_id,
        query=query,
        limit=limit,
    )
    return [DocumentSearchHitResponse.model_validate(item) for item in results]
