from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation, Message

DEFAULT_CONVERSATION_TITLE = "新对话"


def auto_title_from_message(message: str) -> str:
    trimmed = " ".join(message.strip().split())
    if not trimmed:
        return DEFAULT_CONVERSATION_TITLE
    if len(trimmed) <= 30:
        return trimmed
    return f"{trimmed[:30]}…"


def default_conversation_title(now: datetime | None = None) -> str:
    current = now or datetime.now(UTC)
    return f"{DEFAULT_CONVERSATION_TITLE} {current.strftime('%m/%d %H:%M')}"


def is_default_conversation_title(title: str) -> bool:
    stripped = title.strip()
    if stripped == DEFAULT_CONVERSATION_TITLE:
        return True
    return stripped.startswith(f"{DEFAULT_CONVERSATION_TITLE} ")


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


async def get_conversation_meta(
    session: AsyncSession,
    *,
    conversation_id: UUID,
) -> tuple[int, str | None]:
    message_count = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(Message.conversation_id == conversation_id)
    )
    count = int(message_count or 0)
    if count == 0:
        return 0, None

    last_message = await session.scalar(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    if last_message is None:
        return count, None

    preview = " ".join(last_message.content.strip().split())
    if not preview:
        return count, None
    if len(preview) <= 80:
        return count, preview
    return count, f"{preview[:80]}…"


async def maybe_auto_title_conversation(
    session: AsyncSession,
    *,
    conversation: Conversation,
    message: str,
) -> Conversation:
    if not is_default_conversation_title(conversation.title):
        return conversation

    existing_user_count = await session.scalar(
        select(func.count())
        .select_from(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.role == "user",
        )
    )
    if int(existing_user_count or 0) > 0:
        return conversation

    new_title = auto_title_from_message(message)
    if new_title == DEFAULT_CONVERSATION_TITLE:
        return conversation

    conversation.title = new_title
    conversation.updated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(conversation)
    return conversation


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
