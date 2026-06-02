from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "memory@example.com", "username": "memory", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "memory@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_key_memory_is_created_as_review_item_then_approved() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Memory Book"}).json()

    draft = client.post(
        f"/novels/{novel['id']}/memory-review-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "Protagonist constraint",
            "body": "The protagonist must never willingly betray a patient.",
            "importance": 100,
        },
    )

    assert draft.status_code == 201
    approved = client.post(
        f"/memory-review-items/{draft.json()['id']}/approve",
        headers=headers,
    )

    assert approved.status_code == 200
    assert approved.json()["memory_type"] == "key_memory"
    assert approved.json()["importance"] == 100
