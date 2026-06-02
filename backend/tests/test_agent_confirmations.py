from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "agent@example.com", "username": "agent", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "agent@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_agent_rewrite_creates_confirmation_and_apply_updates_document() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Agent Book"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()
    client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={"content": {"type": "doc", "content": [{"type": "paragraph", "text": "Calm room."}]}},
    )

    response = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={
            "message": "Rewrite the selected paragraph to feel more tense.",
            "document_id": chapter["document_id"],
            "selected_text": "Calm room.",
        },
    )

    assert response.status_code == 200
    confirmation_id = response.json()["confirmation"]["id"]
    applied = client.post(f"/confirmations/{confirmation_id}/approve", headers=headers)
    assert applied.status_code == 200
    document = client.get(f"/documents/{chapter['document_id']}", headers=headers).json()
    assert "tense" in str(document["content"]).lower()
