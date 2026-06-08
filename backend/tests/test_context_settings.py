from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "ctx@example.com", "username": "ctx", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "ctx@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_context_settings_defaults(client: TestClient | None = None) -> None:
    client = client or TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Context Novel"}).json()

    response = client.get(f"/novels/{novel['id']}/context-settings", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["sources"]["key_memories"] is True
    assert body["budget"]["recent_chapters_count"] == 3


def test_context_settings_patch(client: TestClient | None = None) -> None:
    client = client or TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Patch Novel"}).json()

    response = client.patch(
        f"/novels/{novel['id']}/context-settings",
        headers=headers,
        json={"sources": {"rag_search": False}},
    )
    assert response.status_code == 200
    assert response.json()["sources"]["rag_search"] is False
    assert response.json()["sources"]["key_memories"] is True
