from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient, email: str = "review@example.com") -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": email, "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_confirmation_items_can_be_listed_and_rejected() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Review Novel"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()
    confirmation = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=headers,
        json={
            "message": "Rewrite this paragraph",
            "document_id": chapter["document_id"],
            "selected_text": "The room was quiet.",
        },
    ).json()["confirmation"]

    listed = client.get(f"/novels/{novel['id']}/confirmations", headers=headers)
    rejected = client.post(f"/confirmations/{confirmation['id']}/reject", headers=headers)

    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [confirmation["id"]]
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_memory_review_items_can_be_listed_and_rejected() -> None:
    client = TestClient(app)
    headers = auth_headers(client, "memory-review@example.com")
    novel = client.post("/novels", headers=headers, json={"title": "Memory Novel"}).json()
    item = client.post(
        f"/novels/{novel['id']}/memory-review-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "Core vow",
            "body": "Never forget the lighthouse.",
            "importance": 90,
        },
    ).json()

    listed = client.get(f"/novels/{novel['id']}/memory-review-items", headers=headers)
    rejected = client.post(f"/memory-review-items/{item['id']}/reject", headers=headers)

    assert listed.status_code == 200
    assert [entry["id"] for entry in listed.json()] == [item["id"]]
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
