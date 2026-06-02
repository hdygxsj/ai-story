from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.crypto import encrypt_api_key
from app.db.session import get_session
from app.models import ModelProfile, User
from app.schemas.model_profile import ModelProfileCreate, ModelProfileResponse


router = APIRouter(prefix="/model-profiles", tags=["model-profiles"])


@router.post("", response_model=ModelProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_model_profile(
    payload: ModelProfileCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ModelProfile:
    model_profile = ModelProfile(
        owner_id=current_user.id,
        name=payload.name,
        provider_kind=payload.provider_kind,
        base_url=payload.base_url,
        api_key_ciphertext=encrypt_api_key(payload.api_key),
        chat_model=payload.chat_model,
        writing_model=payload.writing_model,
        summary_model=payload.summary_model,
        embedding_model=payload.embedding_model,
        supports_tool_calling=payload.supports_tool_calling,
        supports_json_mode=payload.supports_json_mode,
        supports_streaming=payload.supports_streaming,
        context_window=payload.context_window,
        embedding_dimensions=payload.embedding_dimensions,
        extra_headers=payload.extra_headers,
    )
    session.add(model_profile)
    await session.commit()
    await session.refresh(model_profile)
    return model_profile


@router.get("", response_model=list[ModelProfileResponse])
async def list_model_profiles(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ModelProfile]:
    result = await session.scalars(
        select(ModelProfile)
        .where(ModelProfile.owner_id == current_user.id)
        .order_by(ModelProfile.created_at, ModelProfile.id)
    )
    return list(result)
