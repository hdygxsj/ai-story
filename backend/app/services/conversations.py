from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message


def auto_title_from_message(message: str) -> str:
    trimmed = message.strip()
    if not trimmed:
        return "新对话"
    return trimmed[:30]


async def create_conversation(
    session: AsyncSession,
    *,
    novel_id: UUID,
    user_id: UUID,
    title: str,
) -> Conversation:
    now = datetime.now(UTC)
    conversation = Conversation(
        novel_id=novel_id,
        user_id=user_id,
        title=title,
        created_at=now,
        updated_at=now,
    )
    session.add(conversation)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def list_conversations(session: AsyncSession, *, novel_id: UUID) -> list[Conversation]:
    conversations = await session.scalars(
        select(Conversation)
        .where(Conversation.novel_id == novel_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id)
    )
    return list(conversations)


async def get_conversation(
    session: AsyncSession,
    *,
    novel_id: UUID,
    conversation_id: UUID,
) -> Conversation:
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.novel_id == novel_id,
        )
    )
    if conversation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conversation


async def update_conversation_title(
    session: AsyncSession,
    *,
    novel_id: UUID,
    conversation_id: UUID,
    title: str,
) -> Conversation:
    conversation = await get_conversation(session, novel_id=novel_id, conversation_id=conversation_id)
    conversation.title = title
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(conversation)
    return conversation


async def delete_conversation(
    session: AsyncSession,
    *,
    novel_id: UUID,
    conversation_id: UUID,
) -> None:
    conversation = await get_conversation(session, novel_id=novel_id, conversation_id=conversation_id)
    await session.delete(conversation)
    await session.commit()


async def list_messages(session: AsyncSession, *, conversation_id: UUID) -> list[Message]:
    messages = await session.scalars(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at, Message.id)
    )
    return list(messages)


async def append_message(
    session: AsyncSession,
    *,
    conversation: Conversation,
    role: str,
    content: str,
    metadata: dict[str, Any] | None = None,
) -> Message:
    message = Message(
        conversation_id=conversation.id,
        role=role,
        content=content,
        extra_metadata=metadata or {},
    )
    session.add(message)
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(message)
    await session.refresh(conversation)
    return message


async def resolve_conversation_for_message(
    session: AsyncSession,
    *,
    novel_id: UUID,
    user_id: UUID,
    conversation_id: UUID | None,
    message: str,
) -> Conversation:
    if conversation_id is not None:
        return await get_conversation(session, novel_id=novel_id, conversation_id=conversation_id)
    return await create_conversation(
        session,
        novel_id=novel_id,
        user_id=user_id,
        title=auto_title_from_message(message),
    )
