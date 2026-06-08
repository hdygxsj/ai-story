from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_session
from app.models import User
from app.schemas.context import (
    ContextBudgetSettings,
    ContextSettingsResponse,
    ContextSettingsUpdate,
    ContextSources,
)
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    ConversationUpdate,
    MessageResponse,
)
from app.services.context_settings import get_or_create_context_settings, update_context_settings
from app.services.conversations import (
    auto_title_from_message,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_messages,
    update_conversation_title,
)
from app.services.novels import get_owned_novel

router = APIRouter(tags=["conversations"])


@router.get("/novels/{novel_id}/conversations", response_model=list[ConversationResponse])
async def get_novel_conversations(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[ConversationResponse]:
    await get_owned_novel(session, current_user, novel_id)
    conversations = await list_conversations(session, novel_id=novel_id)
    return [ConversationResponse.model_validate(item) for item in conversations]


@router.post(
    "/novels/{novel_id}/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def post_novel_conversation(
    novel_id: UUID,
    payload: ConversationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationResponse:
    await get_owned_novel(session, current_user, novel_id)
    conversation = await create_conversation(
        session,
        novel_id=novel_id,
        user_id=current_user.id,
        title=payload.title or "新对话",
    )
    return ConversationResponse.model_validate(conversation)


@router.get("/novels/{novel_id}/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_novel_conversation(
    novel_id: UUID,
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationResponse:
    await get_owned_novel(session, current_user, novel_id)
    conversation = await get_conversation(session, novel_id=novel_id, conversation_id=conversation_id)
    return ConversationResponse.model_validate(conversation)


@router.patch("/novels/{novel_id}/conversations/{conversation_id}", response_model=ConversationResponse)
async def patch_novel_conversation(
    novel_id: UUID,
    conversation_id: UUID,
    payload: ConversationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ConversationResponse:
    await get_owned_novel(session, current_user, novel_id)
    conversation = await update_conversation_title(
        session,
        novel_id=novel_id,
        conversation_id=conversation_id,
        title=payload.title,
    )
    return ConversationResponse.model_validate(conversation)


@router.delete("/novels/{novel_id}/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_novel_conversation(
    novel_id: UUID,
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    await get_owned_novel(session, current_user, novel_id)
    await delete_conversation(session, novel_id=novel_id, conversation_id=conversation_id)


@router.get(
    "/novels/{novel_id}/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
async def get_conversation_messages(
    novel_id: UUID,
    conversation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[MessageResponse]:
    await get_owned_novel(session, current_user, novel_id)
    await get_conversation(session, novel_id=novel_id, conversation_id=conversation_id)
    messages = await list_messages(session, conversation_id=conversation_id)
    return [MessageResponse.model_validate(item) for item in messages]


@router.get("/novels/{novel_id}/context-settings", response_model=ContextSettingsResponse)
async def get_novel_context_settings(
    novel_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContextSettingsResponse:
    novel = await get_owned_novel(session, current_user, novel_id)
    settings = await get_or_create_context_settings(session, novel=novel)
    return ContextSettingsResponse(
        novel_id=settings.novel_id,
        sources=ContextSources.model_validate(settings.sources),
        budget=ContextBudgetSettings.model_validate(settings.budget),
        updated_at=settings.updated_at.isoformat(),
    )


@router.patch("/novels/{novel_id}/context-settings", response_model=ContextSettingsResponse)
async def patch_novel_context_settings(
    novel_id: UUID,
    payload: ContextSettingsUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ContextSettingsResponse:
    novel = await get_owned_novel(session, current_user, novel_id)
    settings = await update_context_settings(
        session,
        novel=novel,
        sources=payload.sources.model_dump() if payload.sources else None,
        budget=payload.budget.model_dump() if payload.budget else None,
    )
    return ContextSettingsResponse(
        novel_id=settings.novel_id,
        sources=ContextSources.model_validate(settings.sources),
        budget=ContextBudgetSettings.model_validate(settings.budget),
        updated_at=settings.updated_at.isoformat(),
    )
