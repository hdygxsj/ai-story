from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tool_runtime import build_runtime_tools
from app.agent.runtime import invoke_agent_graph, stream_agent_graph
from app.main import app
from app.models import Document, MemoryItem, Novel, RagChunk, User, WorkspaceNode


@pytest.mark.asyncio
async def test_invoke_agent_graph_builds_tools_with_authenticated_scope(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = uuid4()
    novel_id = uuid4()
    captured: dict[str, object] = {}

    async def fake_get_checkpointer() -> object:
        return object()

    def fake_build_runtime_tools(
        runtime_session: AsyncSession,
        *,
        model_profile: object,
        owner_id: UUID,
        novel_id: UUID,
        document_id: UUID | None,
    ) -> list[object]:
        captured.update(
            session=runtime_session,
            model_profile=model_profile,
            owner_id=owner_id,
            novel_id=novel_id,
            document_id=document_id,
        )
        return []

    class FakeGraph:
        async def ainvoke(self, state: dict[str, object], config: dict[str, object]) -> dict[str, object]:
            captured.update(state=state, config=config)
            return {"response": "ok"}

    monkeypatch.setattr("app.agent.runtime.get_checkpointer", fake_get_checkpointer)
    monkeypatch.setattr("app.agent.runtime.build_runtime_tools", fake_build_runtime_tools)
    monkeypatch.setattr(
        "app.agent.runtime.build_agent_graph",
        lambda *, tools, checkpointer, model_profile: FakeGraph(),
    )

    document_id = uuid4()
    state = {"novel_id": uuid4(), "document_id": document_id, "message": "Remember this."}
    result = await invoke_agent_graph(
        session,
        state=state,
        model_profile=None,
        owner_id=owner_id,
        novel_id=novel_id,
    )

    assert result == {"response": "ok"}
    assert captured["session"] is session
    assert captured["owner_id"] == owner_id
    assert captured["novel_id"] == novel_id
    assert captured["document_id"] == document_id
    assert captured["state"] == state


@pytest.mark.asyncio
async def test_stream_agent_graph_builds_tools_with_current_document_scope(
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id = uuid4()
    novel_id = uuid4()
    document_id = uuid4()
    captured: dict[str, object] = {}

    async def fake_get_checkpointer() -> object:
        return object()

    def fake_build_runtime_tools(
        runtime_session: AsyncSession,
        *,
        model_profile: object,
        owner_id: UUID,
        novel_id: UUID,
        document_id: UUID | None,
    ) -> list[object]:
        captured.update(
            session=runtime_session,
            model_profile=model_profile,
            owner_id=owner_id,
            novel_id=novel_id,
            document_id=document_id,
        )
        return []

    class FakeGraph:
        async def astream_events(
            self, state: dict[str, object], config: dict[str, object], version: str
        ):
            captured.update(state=state, config=config, version=version)
            yield {"event": "on_chain_end", "name": "LangGraph", "data": {"output": {"response": "ok"}}}

    monkeypatch.setattr("app.agent.runtime.get_checkpointer", fake_get_checkpointer)
    monkeypatch.setattr("app.agent.runtime.build_runtime_tools", fake_build_runtime_tools)
    monkeypatch.setattr(
        "app.agent.runtime.build_agent_graph",
        lambda *, tools, checkpointer, model_profile: FakeGraph(),
    )

    events = [
        event
        async for event in stream_agent_graph(
            session,
            state={"novel_id": novel_id, "document_id": document_id, "message": "Stream."},
            model_profile=None,
            owner_id=owner_id,
            novel_id=novel_id,
        )
    ]

    assert events == [("done", {"response": "ok", "tool_calls": []})]
    assert captured["session"] is session
    assert captured["owner_id"] == owner_id
    assert captured["novel_id"] == novel_id
    assert captured["document_id"] == document_id


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "tool@example.com", "username": "tool", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "tool@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_runtime_search_memory_returns_approved_items(session: AsyncSession) -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Tool Novel"}).json()

    session.add(
        MemoryItem(
            novel_id=UUID(novel["id"]),
            memory_type="key_memory",
            title="誓言",
            body="主角不能背叛病人。",
            importance=90,
        )
    )
    await session.commit()

    tools = build_runtime_tools(session, model_profile=None)
    search_tool = next(tool for tool in tools if tool.name == "search_memory")
    result = await search_tool.ainvoke({"novel_id": novel["id"], "query": "背叛", "limit": 8})

    assert result["results"]
    assert any("背叛" in entry["body"] for entry in result["results"])


@pytest.mark.asyncio
async def test_runtime_tools_default_to_current_novel_and_document_scope(
    session: AsyncSession,
) -> None:
    owner = User(email="current-tool@example.com", username="current-tool", password_hash="hash")
    session.add(owner)
    await session.flush()
    novel = Novel(owner_id=owner.id, title="Current Defaults")
    session.add(novel)
    await session.flush()
    document = Document(
        novel_id=novel.id,
        content={"type": "doc", "content": [{"type": "text", "text": "旧正文"}]},
    )
    session.add(document)
    await session.flush()
    session.add_all(
        [
            WorkspaceNode(
                novel_id=novel.id,
                title="当前章节",
                node_type="chapter",
                document_id=document.id,
                status="active",
            ),
            MemoryItem(
                novel_id=novel.id,
                memory_type="key_memory",
                title="血鹰",
                body="血鹰只属于当前小说。",
                importance=90,
            ),
        ]
    )
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=owner.id,
            novel_id=novel.id,
            document_id=document.id,
        )
    }

    memory_result = await tools["search_memory"].ainvoke({"query": "血鹰", "limit": 5})
    nodes_result = await tools["list_workspace_nodes"].ainvoke({})
    read_result = await tools["read_document"].ainvoke({})
    write_result = await tools["write_document_content"].ainvoke({"content": "新正文"})

    assert [entry["title"] for entry in memory_result["results"]] == ["血鹰"]
    assert [entry["title"] for entry in nodes_result["nodes"]] == ["当前章节"]
    assert read_result == {
        "status": "ok",
        "document_id": str(document.id),
        "content": "旧正文",
    }
    assert write_result["status"] == "ok"
    assert write_result["document_id"] == str(document.id)


@pytest.mark.asyncio
async def test_runtime_tools_cannot_cross_authenticated_novel_scope(session: AsyncSession) -> None:
    current_owner = User(
        email="current-scope@example.com",
        username="current-scope",
        password_hash="hash",
    )
    other_owner = User(
        email="other-scope@example.com",
        username="other-scope",
        password_hash="hash",
    )
    session.add_all([current_owner, other_owner])
    await session.flush()
    current_novel = Novel(owner_id=current_owner.id, title="Current Scope")
    other_novel = Novel(owner_id=other_owner.id, title="Other Scope")
    session.add_all([current_novel, other_novel])
    await session.flush()

    current_document = Document(
        novel_id=current_novel.id,
        content={"type": "doc", "content": [{"type": "text", "text": "current document"}]},
    )
    other_document = Document(
        novel_id=other_novel.id,
        content={"type": "doc", "content": [{"type": "text", "text": "other document"}]},
    )
    session.add_all([current_document, other_document])
    await session.flush()
    session.add_all(
        [
            WorkspaceNode(
                novel_id=current_novel.id,
                title="Current chapter",
                node_type="chapter",
                document_id=current_document.id,
                status="active",
            ),
            WorkspaceNode(
                novel_id=other_novel.id,
                title="Other chapter",
                node_type="chapter",
                document_id=other_document.id,
                status="active",
            ),
        ]
    )
    session.add_all(
        [
            MemoryItem(
                novel_id=current_novel.id,
                memory_type="key_memory",
                title="Current secret",
                body="Only the current novel may read this.",
                importance=90,
            ),
            MemoryItem(
                novel_id=other_novel.id,
                memory_type="key_memory",
                title="Other secret",
                body="The model must not read this.",
                importance=90,
            ),
            RagChunk(
                novel_id=current_novel.id,
                source_type="document",
                source_id=str(current_document.id),
                text="current rag secret",
                embedding=[1.0] + [0.0] * 63,
            ),
            RagChunk(
                novel_id=other_novel.id,
                source_type="document",
                source_id=str(other_document.id),
                text="other rag secret",
                embedding=[1.0] + [0.0] * 63,
            ),
        ]
    )
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=current_owner.id,
            novel_id=current_novel.id,
        )
    }

    memory_result = await tools["search_memory"].ainvoke(
        {"novel_id": str(other_novel.id), "query": "secret", "limit": 8}
    )
    rag_result = await tools["search_rag"].ainvoke(
        {"novel_id": str(other_novel.id), "query": "secret", "limit": 8}
    )
    document_result = await tools["read_document"].ainvoke(
        {"document_id": str(other_document.id)}
    )
    current_document_result = await tools["read_document"].ainvoke(
        {"document_id": str(current_document.id)}
    )
    save_result = await tools["save_key_memory"].ainvoke(
        {
            "novel_id": str(other_novel.id),
            "title": "Scoped save",
            "body": "This must belong to the current novel.",
            "importance": 85,
        }
    )

    assert [entry["title"] for entry in memory_result["results"]] == ["Current secret"]
    assert [entry["text"] for entry in rag_result["results"]] == ["current rag secret"]
    assert document_result == {"status": "error", "message": "文档不存在。"}
    assert current_document_result == {
        "document_id": str(current_document.id),
        "content": "current document",
        "status": "ok",
    }
    assert save_result["status"] == "ok"

    saved = list(
        await session.scalars(select(MemoryItem).where(MemoryItem.title == "Scoped save"))
    )
    assert len(saved) == 1
    assert saved[0].novel_id == current_novel.id

    wrong_owner_tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=other_owner.id,
            novel_id=current_novel.id,
        )
    }
    wrong_owner_document_result = await wrong_owner_tools["read_document"].ainvoke(
        {"document_id": str(current_document.id)}
    )
    assert wrong_owner_document_result == {"status": "error", "message": "文档不存在。"}


@pytest.mark.asyncio
@pytest.mark.parametrize("missing_scope", ["owner", "novel"])
async def test_save_key_memory_fails_closed_without_authenticated_scope(
    session: AsyncSession,
    missing_scope: str,
) -> None:
    owner = User(email=f"missing-{missing_scope}@example.com", username=f"missing-{missing_scope}", password_hash="hash")
    session.add(owner)
    await session.flush()
    novel = Novel(owner_id=owner.id, title=f"Missing {missing_scope}")
    session.add(novel)
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=None if missing_scope == "owner" else owner.id,
            novel_id=None if missing_scope == "novel" else novel.id,
        )
    }
    result = await tools["save_key_memory"].ainvoke(
        {
            "novel_id": str(novel.id),
            "title": "Must not save",
            "body": "Authenticated scope is required.",
            "importance": 90,
        }
    )

    assert result["status"] == "error"
    assert "authenticated" in result["message"].lower()
    assert list(await session.scalars(select(MemoryItem))) == []


@pytest.mark.asyncio
async def test_runtime_update_novel_renames_title(session: AsyncSession) -> None:
    owner = User(email="rename-agent@example.com", username="rename-agent", password_hash="hash")
    session.add(owner)
    await session.flush()
    novel = Novel(owner_id=owner.id, title="旧书名")
    session.add(novel)
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session,
            model_profile=None,
            owner_id=owner.id,
            novel_id=novel.id,
        )
    }
    result = await tools["update_novel"].ainvoke({"novel_id": str(novel.id), "title": "新书名"})

    assert result["status"] == "ok"
    assert result["novel_updated"]["title"] == "新书名"
    refreshed = await session.scalar(select(Novel).where(Novel.id == novel.id))
    assert refreshed is not None
    assert refreshed.title == "新书名"
