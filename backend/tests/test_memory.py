from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models import MemoryItem, Novel, RagChunk, User
from app.services.memory import create_memory_item, delete_memory_item


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "memory@example.com", "username": "memory", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "memory@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_key_memory_is_created_as_review_item_then_approved() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Memory Book"}).json()

    draft = client.post(
        f"/novels/{novel['id']}/memory-review-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "Protagonist constraint",
            "body": "The protagonist must never willingly betray a patient.",
            "importance": 100,
        },
    )

    assert draft.status_code == 201
    approved = client.post(
        f"/memory-review-items/{draft.json()['id']}/approve",
        headers=headers,
    )

    assert approved.status_code == 200
    assert approved.json()["memory_type"] == "key_memory"
    assert approved.json()["importance"] == 100


@pytest.mark.asyncio
async def test_create_memory_item_persists_memory_and_rag_chunk(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = User(
        email="create-memory@example.com",
        username="create-memory",
        password_hash="hashed",
    )
    session.add(owner)
    await session.flush()
    novel = Novel(owner_id=owner.id, title="Created Memory Novel")
    session.add(novel)
    await session.flush()

    commit = AsyncMock()
    with monkeypatch.context() as patch:
        patch.setattr(session, "commit", commit)
        memory = await create_memory_item(
            session,
            novel_id=novel.id,
            memory_type="key_memory",
            title="A binding promise",
            body="The protagonist always protects the clinic.",
            importance=85,
            metadata={
                "origin": "test",
                "memory_type": "caller-value",
                "importance": -1,
            },
        )
        commit.assert_not_awaited()

    await session.commit()

    stored_memory = await session.scalar(select(MemoryItem).where(MemoryItem.id == memory.id))
    stored_chunk = await session.scalar(
        select(RagChunk).where(
            RagChunk.novel_id == novel.id,
            RagChunk.source_type == "memory",
            RagChunk.source_id == str(memory.id),
        )
    )

    assert stored_memory is memory
    assert stored_memory.extra_metadata == {
        "origin": "test",
        "memory_type": "caller-value",
        "importance": -1,
    }
    assert stored_chunk is not None
    assert stored_chunk.novel_id == novel.id
    assert stored_chunk.text == "A binding promise\nThe protagonist always protects the clinic."
    assert stored_chunk.extra_metadata == {
        "memory_type": "key_memory",
        "importance": 85,
        "origin": "test",
    }


@pytest.mark.asyncio
async def test_delete_memory_item_removes_memory_and_rag_chunk(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner = User(
        email="delete-memory@example.com",
        username="delete-memory",
        password_hash="hashed",
    )
    session.add(owner)
    await session.flush()
    novel = Novel(owner_id=owner.id, title="Deleted Memory Novel")
    other_owner = User(
        email="other-memory@example.com",
        username="other-memory",
        password_hash="hashed",
    )
    session.add(other_owner)
    await session.flush()
    other_novel = Novel(owner_id=other_owner.id, title="Other Owner Novel")
    session.add_all([novel, other_novel])
    await session.flush()
    memory = await create_memory_item(
        session,
        novel_id=novel.id,
        memory_type="key_memory",
        title="Temporary memory",
        body="This memory should be removed.",
    )
    different_type_chunk = RagChunk(
        novel_id=novel.id,
        source_type="context_snapshot",
        source_id=str(memory.id),
        text="Keep same source id with a different type.",
        embedding=[0.0] * 64,
    )
    other_novel_chunk = RagChunk(
        novel_id=other_novel.id,
        source_type="memory",
        source_id=str(memory.id),
        text="Keep same source id in another novel.",
        embedding=[0.0] * 64,
    )
    session.add_all([different_type_chunk, other_novel_chunk])
    await session.commit()

    assert await delete_memory_item(session, owner_id=other_owner.id, item_id=memory.id) is False
    assert await session.get(MemoryItem, memory.id) is memory

    commit = AsyncMock()
    with monkeypatch.context() as patch:
        patch.setattr(session, "commit", commit)
        deleted = await delete_memory_item(session, owner_id=owner.id, item_id=memory.id)
        commit.assert_not_awaited()

    await session.commit()
    await session.flush()

    assert deleted is True
    assert await session.get(MemoryItem, memory.id) is None
    assert await session.scalar(
        select(RagChunk).where(
            RagChunk.novel_id == novel.id,
            RagChunk.source_type == "memory",
            RagChunk.source_id == str(memory.id),
        )
    ) is None
    assert await session.get(RagChunk, different_type_chunk.id) is different_type_chunk
    assert await session.get(RagChunk, other_novel_chunk.id) is other_novel_chunk
    assert await delete_memory_item(session, owner_id=other_owner.id, item_id=memory.id) is False
