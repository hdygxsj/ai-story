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
        json={
            "content": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Calm room. The window stayed open."}],
                    }
                ],
            }
        },
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
    assert applied.json()["document_id"] == chapter["document_id"]
    document = client.get(f"/documents/{chapter['document_id']}", headers=headers).json()
    assert "tense" in str(document["content"]).lower()
    assert "The window stayed open." in str(document["content"])


def test_agent_rewrite_confirmation_rejects_stale_document() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Stale Book"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()
    original = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Calm room."}]}],
    }
    client.patch(f"/documents/{chapter['document_id']}", headers=headers, json={"content": original})
    proposal = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={
            "message": "Rewrite the selected paragraph to feel more tense.",
            "document_id": chapter["document_id"],
            "selected_text": "Calm room.",
        },
    ).json()

    client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={
            "content": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "User edit."}]}],
            }
        },
    )
    applied = client.post(
        f"/confirmations/{proposal['confirmation']['id']}/approve",
        headers=headers,
    )

    assert applied.status_code == 409
    document = client.get(f"/documents/{chapter['document_id']}", headers=headers).json()
    assert "User edit." in str(document["content"])


def test_agent_cleanup_deletes_folders_and_moves_chapters_to_root() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Cleanup Book"}).json()
    folder = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "新文件夹", "node_type": "folder", "parent_id": None},
    ).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "第一章", "node_type": "chapter", "parent_id": folder["id"]},
    ).json()

    response = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={"message": "先帮我删掉已有的文件夹"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["confirmation"] is None
    assert body["workspace_diff"] is not None
    assert any(change["action"] == "trash" for change in body["workspace_diff"]["changes"])
    assert any(change["node_id"] == folder["id"] for change in body["workspace_diff"]["changes"])

    nodes = client.get(f"/novels/{novel['id']}/nodes", headers=headers).json()
    by_id = {node["id"]: node for node in nodes}
    assert by_id[folder["id"]]["status"] == "trashed"
    assert by_id[chapter["id"]]["parent_id"] is None


def test_agent_cleanup_chapters_phrase_applies_workspace_cleanup() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Cleanup Chapters"}).json()
    empty_chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "新章节", "node_type": "chapter", "parent_id": None},
    ).json()
    written_chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "第一章", "node_type": "chapter", "parent_id": None},
    ).json()
    client.patch(
        f"/documents/{written_chapter['document_id']}",
        headers=headers,
        json={"content": {"type": "doc", "content": [{"type": "paragraph", "text": "已有正文"}]}},
    )

    response = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={"message": "清理一下章节"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["workspace_diff"] is not None
    assert any(change["node_id"] == empty_chapter["id"] for change in body["workspace_diff"]["changes"])

    nodes = client.get(f"/novels/{novel['id']}/nodes", headers=headers).json()
    by_id = {node["id"]: node for node in nodes}
    assert by_id[empty_chapter["id"]]["status"] == "trashed"
    assert by_id[written_chapter["id"]]["status"] != "trashed"

    followup = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={"message": "有正文的也删除"},
    )

    assert followup.status_code == 200
    followup_body = followup.json()
    assert followup_body["workspace_diff"] is not None
    nodes = client.get(f"/novels/{novel['id']}/nodes", headers=headers).json()
    by_id = {node["id"]: node for node in nodes}
    assert by_id[written_chapter["id"]]["status"] == "trashed"


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
