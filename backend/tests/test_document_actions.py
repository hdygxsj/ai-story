from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Document, DocumentVersion, Novel, User, WorkspaceNode
from app.services.document_actions import (
    approve_document_confirmation,
    create_document_update_proposal,
    create_selection_replace_proposal,
    create_version_restore_proposal,
    list_owned_document_versions,
)
from app.services.rag import extract_text_from_prosemirror


def document_body(text: str) -> dict:
    return {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}]}


async def create_owned_document(session, *, text: str = "旧正文"):
    user = User(email=f"{uuid4()}@example.com", username=str(uuid4()), password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Scoped Novel")
    session.add(novel)
    await session.flush()
    document = Document(novel_id=novel.id, content=document_body(text))
    session.add(document)
    await session.flush()
    node = WorkspaceNode(
        novel_id=novel.id,
        document_id=document.id,
        title="第一章",
        node_type="chapter",
    )
    session.add(node)
    await session.commit()
    return user, novel, document


async def test_document_update_proposal_does_not_mutate_until_approved(session, monkeypatch) -> None:
    async def fake_index_text(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.document_actions.index_text", fake_index_text)
    user, novel, document = await create_owned_document(session)

    confirmation = await create_document_update_proposal(
        session,
        owner_id=user.id,
        novel_id=novel.id,
        document_id=document.id,
        content="新正文",
    )

    await session.refresh(document)
    assert extract_text_from_prosemirror(document.content) == "旧正文"
    assert confirmation.action_type == "document_update"
    assert confirmation.payload["expected_updated_at"]

    result = await approve_document_confirmation(session, owner_id=user.id, confirmation=confirmation)

    await session.refresh(document)
    versions = list(
        await session.scalars(select(DocumentVersion).where(DocumentVersion.document_id == document.id))
    )
    assert result["document_id"] == str(document.id)
    assert extract_text_from_prosemirror(document.content) == "新正文"
    assert extract_text_from_prosemirror(versions[0].content) == "旧正文"


async def test_selection_replace_changes_only_unique_selection(session, monkeypatch) -> None:
    async def fake_index_text(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.document_actions.index_text", fake_index_text)
    user, novel, document = await create_owned_document(session, text="甲来到门前。乙留在屋内。")
    confirmation = await create_selection_replace_proposal(
        session,
        owner_id=user.id,
        novel_id=novel.id,
        document_id=document.id,
        selected_text="甲来到门前。",
        replacement_text="甲冒雨来到门前。",
    )

    await approve_document_confirmation(session, owner_id=user.id, confirmation=confirmation)

    await session.refresh(document)
    assert extract_text_from_prosemirror(document.content) == "甲冒雨来到门前。乙留在屋内。"


async def test_stale_document_confirmation_is_rejected(session) -> None:
    user, novel, document = await create_owned_document(session)
    confirmation = await create_document_update_proposal(
        session,
        owner_id=user.id,
        novel_id=novel.id,
        document_id=document.id,
        content="Agent 正文",
    )
    document.content = document_body("用户刚刚修改的正文")
    from datetime import UTC, datetime, timedelta

    document.updated_at = datetime.now(UTC) + timedelta(seconds=1)
    await session.commit()

    with pytest.raises(HTTPException) as caught:
        await approve_document_confirmation(session, owner_id=user.id, confirmation=confirmation)

    assert caught.value.status_code == 409


async def test_version_restore_proposal_requires_owned_document(session, monkeypatch) -> None:
    async def fake_index_text(*args, **kwargs):
        return None

    monkeypatch.setattr("app.services.document_actions.index_text", fake_index_text)
    owner, novel, document = await create_owned_document(session, text="当前正文")
    version = DocumentVersion(document_id=document.id, source="user", content=document_body("历史正文"))
    session.add(version)
    outsider = User(email="outsider@example.com", username="outsider", password_hash="hash")
    session.add(outsider)
    await session.commit()

    with pytest.raises(HTTPException) as caught:
        await create_version_restore_proposal(
            session,
            owner_id=outsider.id,
            novel_id=novel.id,
            document_id=document.id,
            version_id=version.id,
        )
    assert caught.value.status_code == 404

    versions = await list_owned_document_versions(
        session, owner_id=owner.id, novel_id=novel.id, document_id=document.id
    )
    assert [item.id for item in versions] == [version.id]

    confirmation = await create_version_restore_proposal(
        session,
        owner_id=owner.id,
        novel_id=novel.id,
        document_id=document.id,
        version_id=version.id,
    )
    await approve_document_confirmation(session, owner_id=owner.id, confirmation=confirmation)
    await session.refresh(document)
    assert extract_text_from_prosemirror(document.content) == "历史正文"
