from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.crypto import encrypt_api_key
from app.db.session import get_session
from app.models import ModelProfile, User
from app.schemas.model_profile import (
    ModelProfileConnectivityResponse,
    ModelProfileConnectivityResult,
    ModelProfileCreate,
    ModelProfileResponse,
    ModelProfileTestRequest,
    ModelProfileUpdate,
)
from app.services.model_profile_connectivity import (
    PURPOSE_LABELS,
    build_test_model_profile,
    run_model_profile_connectivity_tests,
)


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
        chat_provider_kind=payload.chat_provider_kind,
        chat_model=payload.chat_model,
        chat_base_url=payload.chat_base_url,
        chat_api_key_ciphertext=encrypt_api_key(payload.chat_api_key) if payload.chat_api_key else None,
        writing_provider_kind=payload.writing_provider_kind,
        writing_model=payload.writing_model,
        writing_base_url=payload.writing_base_url,
        writing_api_key_ciphertext=encrypt_api_key(payload.writing_api_key) if payload.writing_api_key else None,
        summary_provider_kind=payload.summary_provider_kind,
        summary_model=payload.summary_model,
        summary_base_url=payload.summary_base_url,
        summary_api_key_ciphertext=encrypt_api_key(payload.summary_api_key) if payload.summary_api_key else None,
        embedding_provider_kind=payload.embedding_provider_kind,
        embedding_model=payload.embedding_model or "",
        embedding_base_url=payload.embedding_base_url,
        embedding_api_key_ciphertext=encrypt_api_key(payload.embedding_api_key) if payload.embedding_api_key else None,
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


@router.patch("/{profile_id}", response_model=ModelProfileResponse)
async def update_model_profile(
    profile_id: UUID,
    payload: ModelProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ModelProfile:
    model_profile = await session.scalar(
        select(ModelProfile).where(
            ModelProfile.id == profile_id,
            ModelProfile.owner_id == current_user.id,
        )
    )
    if model_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model profile not found")

    updates = payload.model_dump(exclude_unset=True)
    for field in (
        "name",
        "provider_kind",
        "base_url",
        "chat_provider_kind",
        "chat_model",
        "chat_base_url",
        "writing_provider_kind",
        "writing_model",
        "writing_base_url",
        "summary_provider_kind",
        "summary_model",
        "summary_base_url",
        "embedding_provider_kind",
        "embedding_model",
        "embedding_base_url",
        "supports_tool_calling",
        "supports_json_mode",
        "supports_streaming",
        "context_window",
        "embedding_dimensions",
        "extra_headers",
    ):
        if field in updates:
            setattr(model_profile, field, updates[field])

    if "api_key" in updates and updates["api_key"]:
        model_profile.api_key_ciphertext = encrypt_api_key(updates["api_key"])
    if "chat_api_key" in updates:
        model_profile.chat_api_key_ciphertext = (
            encrypt_api_key(updates["chat_api_key"]) if updates["chat_api_key"] else None
        )
    if "writing_api_key" in updates:
        model_profile.writing_api_key_ciphertext = (
            encrypt_api_key(updates["writing_api_key"]) if updates["writing_api_key"] else None
        )
    if "summary_api_key" in updates:
        model_profile.summary_api_key_ciphertext = (
            encrypt_api_key(updates["summary_api_key"]) if updates["summary_api_key"] else None
        )
    if "embedding_api_key" in updates:
        model_profile.embedding_api_key_ciphertext = (
            encrypt_api_key(updates["embedding_api_key"]) if updates["embedding_api_key"] else None
        )

    await session.commit()
    await session.refresh(model_profile)
    return model_profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_profile(
    profile_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    model_profile = await session.scalar(
        select(ModelProfile).where(
            ModelProfile.id == profile_id,
            ModelProfile.owner_id == current_user.id,
        )
    )
    if model_profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model profile not found")

    await session.delete(model_profile)
    await session.commit()


@router.post("/test-connectivity", response_model=ModelProfileConnectivityResponse)
async def test_model_profile_connectivity(
    payload: ModelProfileTestRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ModelProfileConnectivityResponse:
    stored = None
    if payload.profile_id is not None:
        stored = await session.scalar(
            select(ModelProfile).where(
                ModelProfile.id == payload.profile_id,
                ModelProfile.owner_id == current_user.id,
            )
        )
        if stored is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model profile not found")

    try:
        profile = build_test_model_profile(payload, owner_id=current_user.id, stored=stored)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    results = await run_model_profile_connectivity_tests(profile, purposes=payload.purposes)
    return ModelProfileConnectivityResponse(
        results=[
            ModelProfileConnectivityResult(
                purpose=result.purpose,
                label=PURPOSE_LABELS[result.purpose],
                ok=result.ok,
                message=result.message,
                model=result.model,
            )
            for result in results
        ]
    )
