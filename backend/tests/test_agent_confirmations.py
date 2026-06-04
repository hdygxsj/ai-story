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


def test_agent_directory_organization_applies_workspace_changes_without_confirmation() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Agent Directory Book"}).json()
    drafts = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "草稿", "node_type": "folder", "parent_id": None},
    ).json()
    draft_chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "草稿片段", "node_type": "chapter", "parent_id": None},
    ).json()

    response = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={"message": "帮我整理章节和草稿目录"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confirmation"] is None
    assert body["workspace_diff"]["changes"][0]["node_id"] == draft_chapter["id"]
    assert body["workspace_nodes"]

    nodes = client.get(f"/novels/{novel['id']}/nodes", headers=headers).json()
    by_id = {node["id"]: node for node in nodes}
    assert by_id[draft_chapter["id"]]["parent_id"] == drafts["id"]
