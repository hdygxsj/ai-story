from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from sqlalchemy import select

from app.main import app
from app.models import ContextSnapshot, Conversation, Message, Novel, User
from app.services.context_assembly import assemble_context
from app.services.context_settings import update_context_settings


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "asm@example.com", "username": "asm", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "asm@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_stream_response_includes_context_detail(monkeypatch) -> None:
    search_calls: list[dict] = []

    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            from langchain_core.messages import AIMessage

            return AIMessage(content="我建议从场景氛围入手。")

    async def fake_search_rag(*args, **kwargs):
        search_calls.append(kwargs)
        return []

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    monkeypatch.setattr("app.services.context_assembly.search_rag_chunks", fake_search_rag)

    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Assembly Novel"}).json()
    profile = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Chat profile",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
        },
    ).json()
    client.patch(
        f"/novels/{novel['id']}",
        headers=headers,
        json={"default_model_profile_id": profile["id"]},
    )
    review = client.post(
        f"/novels/{novel['id']}/memory-review-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "誓言",
            "body": "主角不能背叛病人。",
            "importance": 90,
        },
    ).json()
    client.post(f"/memory-review-items/{review['id']}/approve", headers=headers)

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "接下来怎么写？"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "context_detail" in body
    assert "usage_ratio" in body
    assert "key_memory" in body or "上下文占用" in body
    assert any(
        call.get("excluded_source_types")
        == {"character_state", "creative_asset", "relationship_edge", "timeline_event"}
        for call in search_calls
    )


def test_trashed_chapters_are_not_loaded_as_neighboring_context(monkeypatch) -> None:
    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            from langchain_core.messages import AIMessage

            return AIMessage(content="继续。")

    async def fake_search_rag(*args, **kwargs):
        return []

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    monkeypatch.setattr("app.services.context_assembly.search_rag_chunks", fake_search_rag)

    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Trashed Neighbor Novel"}).json()
    profile = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Neighbor profile",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
        },
    ).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Discarded chapter", "node_type": "chapter", "parent_id": None},
    ).json()
    client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={
            "content": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "discarded text"}]}],
            }
        },
    )
    client.patch(
        f"/novels/{novel['id']}/nodes/reorder",
        headers=headers,
        json={
            "items": [
                {
                    "id": chapter["id"],
                    "parent_id": None,
                    "position": 0,
                    "status": "trashed",
                }
            ]
        },
    )
    client.patch(
        f"/novels/{novel['id']}",
        headers=headers,
        json={"default_model_profile_id": profile["id"]},
    )

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "继续写"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"context_detail"' in body
    assert "neighboring_chapter" not in body


def test_relationships_are_loaded_as_structured_context(monkeypatch) -> None:
    model_messages = []

    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            from langchain_core.messages import AIMessage

            model_messages.extend(messages)
            return AIMessage(content="关系已读取。")

    async def fake_search_rag(*args, **kwargs):
        return []

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    monkeypatch.setattr("app.services.context_assembly.search_rag_chunks", fake_search_rag)

    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Relationship Context Novel"}).json()
    profile = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Relationship profile",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
        },
    ).json()
    relationship = client.post(
        f"/novels/{novel['id']}/relationship-edges",
        headers=headers,
        json={
            "source_character": "林舟",
            "target_character": "沈月",
            "relationship_type": "盟友",
            "description": "共同守护灯塔",
            "metadata": {},
        },
    )
    assert relationship.status_code == 201
    client.patch(
        f"/novels/{novel['id']}",
        headers=headers,
        json={"default_model_profile_id": profile["id"]},
    )

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "他们是什么关系？"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "structured_memory" in body
    assert any("共同守护灯塔" in str(message.content) for message in model_messages)


def test_conversation_history_is_passed_as_role_messages_not_system_text(monkeypatch) -> None:
    from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

    model_messages = []

    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            model_messages.extend(messages)
            return AIMessage(content="知道了。")

    async def fake_search_rag(*args, **kwargs):
        return []

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    monkeypatch.setattr("app.services.context_assembly.search_rag_chunks", fake_search_rag)

    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "History Novel"}).json()
    profile = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "History profile",
            "provider_kind": "openai",
            "api_key": "sk-test",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
        },
    ).json()
    client.patch(
        f"/novels/{novel['id']}",
        headers=headers,
        json={"default_model_profile_id": profile["id"]},
    )

    first = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={"message": "前四章是空的"},
    )
    conversation_id = first.json()["conversation_id"]
    model_messages.clear()

    second = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={"message": "把它们补上", "conversation_id": conversation_id},
    )

    assert second.status_code == 200
    assert isinstance(model_messages[0], SystemMessage)
    assert "【对话历史】" not in str(model_messages[0].content)
    assert isinstance(model_messages[-3], HumanMessage)
    assert model_messages[-3].content == "前四章是空的"
    assert isinstance(model_messages[-2], AIMessage)
    assert model_messages[-2].content == "知道了。"
    assert isinstance(model_messages[-1], HumanMessage)
    assert model_messages[-1].content == "把它们补上"


async def test_conversation_history_restores_stored_reasoning_content(session) -> None:
    user = User(email="reasoning-history@example.com", username="reasoning-history", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Reasoning History")
    session.add(novel)
    await session.flush()
    conversation = Conversation(novel_id=novel.id, user_id=user.id, title="Reasoning")
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            Message(conversation_id=conversation.id, role="user", content="上一轮问题"),
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content="上一轮回答",
                extra_metadata={"reasoning_content": "上一轮思考"},
            ),
        ]
    )
    await session.commit()

    assembled = await assemble_context(
        session,
        novel=novel,
        conversation_id=conversation.id,
        document_id=None,
        selected_text=None,
        user_message="继续",
        model_profile=None,
    )

    assistant_history = [
        message for message in assembled.history_messages if isinstance(message, AIMessage)
    ]
    assert assistant_history
    assert assistant_history[-1].additional_kwargs["reasoning_content"] == "上一轮思考"


async def test_conversation_history_excludes_current_message_by_id_not_sort_position(session) -> None:
    from datetime import UTC, datetime
    from uuid import UUID

    user = User(email="history-order@example.com", username="history-order", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="History Order")
    session.add(novel)
    await session.flush()
    conversation = Conversation(novel_id=novel.id, user_id=user.id, title="History Order")
    session.add(conversation)
    await session.flush()

    same_time = datetime(2026, 6, 16, tzinfo=UTC)
    previous_user = Message(
        id=UUID("ffffffff-ffff-ffff-ffff-ffffffffffff"),
        conversation_id=conversation.id,
        role="user",
        content="之前要求：第38章按新设定修改",
        created_at=same_time,
    )
    previous_assistant = Message(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        conversation_id=conversation.id,
        role="assistant",
        content="已经按第38章处理。",
        created_at=same_time,
    )
    current_user = Message(
        id=UUID("00000000-0000-0000-0000-000000000000"),
        conversation_id=conversation.id,
        role="user",
        content="第40章和第49章也同步修改",
        created_at=same_time,
    )
    session.add_all([previous_user, previous_assistant, current_user])
    await session.commit()

    assembled = await assemble_context(
        session,
        novel=novel,
        conversation_id=conversation.id,
        document_id=None,
        selected_text=None,
        user_message=current_user.content,
        model_profile=None,
        message_id=current_user.id,
    )

    history_contents = [message.content for message in assembled.history_messages]
    assert "之前要求：第38章按新设定修改" in history_contents
    assert "已经按第38章处理。" in history_contents
    assert "第40章和第49章也同步修改" not in history_contents


async def test_conversation_history_includes_tool_call_summaries_for_model_context(session) -> None:
    user = User(email="tool-history@example.com", username="tool-history", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Tool History")
    session.add(novel)
    await session.flush()
    conversation = Conversation(novel_id=novel.id, user_id=user.id, title="Tool History")
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            Message(conversation_id=conversation.id, role="user", content="帮我查灯塔资料"),
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content="查到了。",
                extra_metadata={
                    "tool_calls": [
                        {"tool": "search_rag", "status": "ok", "summary": "命中：钥匙藏在镜片下。"},
                        {"tool": "search_memory", "status": "ok", "summary": "记忆：守灯人害怕涨潮。"},
                    ]
                },
            ),
        ]
    )
    await session.commit()

    assembled = await assemble_context(
        session,
        novel=novel,
        conversation_id=conversation.id,
        document_id=None,
        selected_text=None,
        user_message="刚才查到了什么？",
        model_profile=None,
    )

    conversation_history = next(item.text for item in assembled.pack.items if item.source == "conversation_history")
    assert "工具 search_rag: 命中：钥匙藏在镜片下。" in conversation_history
    assert "工具 search_memory: 记忆：守灯人害怕涨潮。" in conversation_history

    assistant_history = [message for message in assembled.history_messages if isinstance(message, AIMessage)]
    assert assistant_history
    assert "工具 search_rag: 命中：钥匙藏在镜片下。" in str(assistant_history[-1].content)


async def test_context_snapshot_captures_recent_messages_and_tool_results_when_context_is_large(session) -> None:
    user = User(email="snapshot-rich@example.com", username="snapshot-rich", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Rich Snapshot")
    session.add(novel)
    await session.flush()
    conversation = Conversation(novel_id=novel.id, user_id=user.id, title="Rich Snapshot")
    session.add(conversation)
    await session.flush()
    await update_context_settings(
        session,
        novel=novel,
        sources={
            "current_document": False,
            "selected_text": False,
            "key_memories": False,
            "structured_assets": False,
            "neighboring_chapters": False,
            "rag_search": False,
            "conversation_history": True,
        },
        budget={"max_context_tokens": 120, "response_reserve": 0, "conversation_history_limit": 20},
    )
    session.add_all(
        [
            Message(conversation_id=conversation.id, role="user", content="扩写第七章，核心是旧码头密钥。"),
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content="我检索了旧码头线索。" + " 长上下文" * 120,
                extra_metadata={
                    "tool_calls": [
                        {"tool": "search_documents_by_keyword", "status": "ok", "summary": "命中：密钥藏在灯塔镜片下。"}
                    ]
                },
            ),
        ]
    )
    await session.commit()

    assembled = await assemble_context(
        session,
        novel=novel,
        conversation_id=conversation.id,
        document_id=None,
        selected_text=None,
        user_message="继续根据刚才的线索写。",
        model_profile=None,
    )

    assert assembled.context_detail.snapshot_id is not None
    snapshot = await session.scalar(select(ContextSnapshot).where(ContextSnapshot.id == assembled.context_detail.snapshot_id))
    assert snapshot is not None
    assert "扩写第七章" in snapshot.summary
    assert "密钥藏在灯塔镜片下" in snapshot.summary
    assert snapshot.facts["tool_results"] == ["search_documents_by_keyword: 命中：密钥藏在灯塔镜片下。"]


async def test_rag_query_uses_current_request_selection_and_recent_context(session, monkeypatch) -> None:
    captured_queries: list[str] = []

    async def fake_search_rag(*args, **kwargs):
        captured_queries.append(kwargs["query"])
        return []

    monkeypatch.setattr("app.services.context_assembly.search_rag_chunks", fake_search_rag)

    user = User(email="rag-query-context@example.com", username="rag-query-context", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="RAG Query Context")
    session.add(novel)
    await session.flush()
    conversation = Conversation(novel_id=novel.id, user_id=user.id, title="RAG Query Context")
    session.add(conversation)
    await session.flush()
    session.add_all(
        [
            Message(conversation_id=conversation.id, role="user", content="查一下旧码头密码。"),
            Message(
                conversation_id=conversation.id,
                role="assistant",
                content="查到了。",
                extra_metadata={"tool_calls": [{"tool": "search_rag", "status": "ok", "summary": "旧码头密码与潮汐钟有关。"}]},
            ),
        ]
    )
    await session.commit()

    await assemble_context(
        session,
        novel=novel,
        conversation_id=conversation.id,
        document_id=None,
        selected_text="他看向灯塔，等待潮水退去。",
        user_message="继续写它",
        model_profile=None,
    )

    assert captured_queries
    assert "继续写它" in captured_queries[-1]
    assert "他看向灯塔" in captured_queries[-1]
    assert "旧码头密码与潮汐钟有关" in captured_queries[-1]
