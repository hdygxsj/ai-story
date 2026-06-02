from fastapi.testclient import TestClient

from app.main import app


def test_mvp_backend_flow() -> None:
    client = TestClient(app)
    client.post(
        "/auth/register",
        json={"email": "mvp@example.com", "username": "mvp", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "mvp@example.com", "password": "secret123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    novel = client.post("/novels", headers=headers, json={"title": "MVP Novel"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()
    client.post(
        f"/novels/{novel['id']}/memory-review-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "Core promise",
            "body": "Never betray the patient.",
            "importance": 100,
        },
    )
    agent = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={
            "message": "Rewrite the selected paragraph to feel more tense.",
            "document_id": chapter["document_id"],
            "selected_text": "The clinic was quiet.",
        },
    )

    assert agent.status_code == 200
    assert agent.json()["confirmation"]["action_type"] == "rewrite_selection"
