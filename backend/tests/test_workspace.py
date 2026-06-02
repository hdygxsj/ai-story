from fastapi.testclient import TestClient

from app.main import app


def auth_headers(
    client: TestClient,
    *,
    email: str = "workspace@example.com",
    username: str = "workspace",
) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "username": username, "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": email, "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_novel_chapter_and_update_document_version() -> None:
    client = TestClient(app)
    headers = auth_headers(client)

    novel = client.post("/novels", headers=headers, json={"title": "Border Doctor"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()

    update = client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={"content": {"type": "doc", "content": [{"type": "paragraph", "text": "Opening."}]}},
    )

    assert update.status_code == 200
    versions = client.get(f"/documents/{chapter['document_id']}/versions", headers=headers)
    assert versions.status_code == 200
    assert len(versions.json()) == 1


def test_folder_node_does_not_create_document() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="folder@example.com", username="folderuser")

    novel = client.post("/novels", headers=headers, json={"title": "Folder Book"}).json()
    folder = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Drafts", "node_type": "folder", "parent_id": None},
    )

    assert folder.status_code == 201
    assert folder.json()["document_id"] is None


def test_document_access_is_scoped_to_owner() -> None:
    client = TestClient(app)
    owner_headers = auth_headers(client, email="owner@example.com", username="owneruser")
    other_headers = auth_headers(client, email="other@example.com", username="otheruser")

    novel = client.post("/novels", headers=owner_headers, json={"title": "Private Book"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=owner_headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()

    response = client.get(f"/documents/{chapter['document_id']}", headers=other_headers)

    assert response.status_code == 404
