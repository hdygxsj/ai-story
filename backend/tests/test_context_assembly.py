from fastapi.testclient import TestClient

from app.main import app


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
    class FakeChatModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            from langchain_core.messages import AIMessage

            return AIMessage(content="我建议从场景氛围入手。")

    async def fake_search_rag(*args, **kwargs):
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
