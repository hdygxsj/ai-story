from fastapi.testclient import TestClient

from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "materials@example.com", "username": "materials", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "materials@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_materials_can_be_created_listed_and_indexed() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Materials Novel"}).json()

    asset = client.post(
        f"/novels/{novel['id']}/creative-assets",
        headers=headers,
        json={
            "asset_type": "character",
            "name": "Mira",
            "summary": "Mira is the lighthouse keeper.",
            "metadata": {"role": "protagonist"},
        },
    )
    timeline = client.post(
        f"/novels/{novel['id']}/timeline-events",
        headers=headers,
        json={"title": "Storm Night", "event_time": "Chapter 3", "summary": "Mira sees the signal."},
    )
    character_state = client.post(
        f"/novels/{novel['id']}/character-states",
        headers=headers,
        json={"character_name": "Mira", "state": "Hiding the map", "scope": "chapter_3"},
    )
    relationship = client.post(
        f"/novels/{novel['id']}/relationship-edges",
        headers=headers,
        json={
            "source_character": "Mira",
            "target_character": "Jon",
            "relationship_type": "distrusts",
            "description": "Mira distrusts Jon after the storm.",
        },
    )

    assert asset.status_code == 201
    assert timeline.status_code == 201
    assert character_state.status_code == 201
    assert relationship.status_code == 201
    assert client.get(f"/novels/{novel['id']}/creative-assets", headers=headers).json()[0]["name"] == "Mira"
    assert client.get(f"/novels/{novel['id']}/timeline-events", headers=headers).json()[0]["title"] == "Storm Night"
    assert client.get(f"/novels/{novel['id']}/character-states", headers=headers).json()[0]["character_name"] == "Mira"
    assert (
        client.get(f"/novels/{novel['id']}/relationship-edges", headers=headers).json()[0]["relationship_type"]
        == "distrusts"
    )

    rag = client.get(f"/novels/{novel['id']}/rag/search?query=lighthouse keeper", headers=headers)
    assert rag.status_code == 200
    assert rag.json()[0]["source_type"] == "creative_asset"
