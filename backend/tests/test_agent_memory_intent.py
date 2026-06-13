import json

from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "mem@example.com", "username": "mem", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "mem@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_draft_key_memory_creates_formal_memory_item() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Memory Intent Novel"}).json()

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "记住：主角不能背叛病人"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "已保存到记忆" in body
    events = [json.loads(line.removeprefix("data: ")) for line in body.splitlines() if line]
    done_event = next(event for event in events if event["type"] == "done")
    assert done_event["context_status"] == ["已保存关键记忆。"]

    memories_response = client.get(f"/novels/{novel['id']}/memory-items", headers=headers)
    reviews_response = client.get(f"/novels/{novel['id']}/memory-review-items", headers=headers)

    assert memories_response.status_code == 200
    assert reviews_response.status_code == 200
    memories = memories_response.json()
    reviews = reviews_response.json()
    memory = next(item for item in memories if "背叛" in item["body"])
    assert reviews == []

    rag_response = client.get(f"/novels/{novel['id']}/rag/search?query=背叛", headers=headers)

    assert rag_response.status_code == 200
    assert any(
        result["source_type"] == "memory" and result["source_id"] == memory["id"]
        for result in rag_response.json()
    )
