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


def test_draft_key_memory_creates_review_item() -> None:
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
    assert "记忆" in body

    reviews = client.get(f"/novels/{novel['id']}/memory-review-items", headers=headers).json()
    assert any("背叛" in item["body"] for item in reviews)
