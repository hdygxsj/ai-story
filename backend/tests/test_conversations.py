from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "conv@example.com", "username": "conv", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "conv@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_conversation_and_list_messages(client: TestClient | None = None) -> None:
    client = client or TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Conversation Novel"}).json()

    created = client.post(
        f"/novels/{novel['id']}/conversations",
        headers=headers,
        json={"title": "第三章改写"},
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    listed = client.get(f"/novels/{novel['id']}/conversations", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["title"] == "第三章改写"

    messages = client.get(
        f"/novels/{novel['id']}/conversations/{conversation_id}/messages",
        headers=headers,
    )
    assert messages.status_code == 200
    assert messages.json() == []


def test_agent_stream_persists_messages(monkeypatch) -> None:
    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            from langchain_core.messages import AIMessage

            return AIMessage(content="我可以帮你继续写下去。")

    monkeypatch.setattr("app.agent.graph.build_chat_model", lambda profile, purpose="chat": FakeChatModel())
    async def fake_search_rag(*args, **kwargs):
        return []

    monkeypatch.setattr("app.services.context_assembly.search_rag_chunks", fake_search_rag)

    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Streaming Novel"}).json()
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

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "帮我规划下一幕"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    assert "conversation_id" in body
    conversations = client.get(f"/novels/{novel['id']}/conversations", headers=headers).json()
    assert len(conversations) == 1
    messages = client.get(
        f"/novels/{novel['id']}/conversations/{conversations[0]['id']}/messages",
        headers=headers,
    ).json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "帮我规划下一幕"
    assert messages[1]["role"] == "assistant"
    assert "继续写" in messages[1]["content"]


def test_generic_stream_uses_authenticated_agent_graph(monkeypatch) -> None:
    captured = {}

    async def fake_invoke_agent_graph(session, *, state, model_profile, owner_id, novel_id, conversation_id):
        captured.update(
            state=state,
            model_profile=model_profile,
            owner_id=owner_id,
            novel_id=novel_id,
            conversation_id=conversation_id,
        )
        return {"response": "已保存关键记忆「雨夜约定」。", "proposed_payload": None}

    async def fake_search_rag(*args, **kwargs):
        return []

    monkeypatch.setattr("app.agent.chat_stream.invoke_agent_graph", fake_invoke_agent_graph)
    monkeypatch.setattr("app.services.context_assembly.search_rag_chunks", fake_search_rag)

    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Tool Streaming Novel"}).json()
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

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "主角从此害怕雨夜，这会影响后续剧情。"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert '"type": "delta"' in body
    assert '"type": "done"' in body
    assert "已保存关键记忆" in body
    assert str(captured["owner_id"]) != ""
    assert str(captured["novel_id"]) == novel["id"]
    assert captured["state"]["context_pack"].items
