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


def test_creative_assets_can_be_updated_and_deleted() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Materials Novel"}).json()

    created = client.post(
        f"/novels/{novel['id']}/creative-assets",
        headers=headers,
        json={
            "asset_type": "character",
            "name": "Mira",
            "summary": "Mira is the lighthouse keeper.",
        },
    ).json()

    updated = client.patch(
        f"/novels/{novel['id']}/creative-assets/{created['id']}",
        headers=headers,
        json={"name": "Mira Vale", "summary": "Mira keeps the northern lighthouse."},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Mira Vale"
    assert updated.json()["summary"] == "Mira keeps the northern lighthouse."

    rag = client.get(f"/novels/{novel['id']}/rag/search?query=northern lighthouse", headers=headers)
    assert rag.status_code == 200
    assert rag.json()[0]["source_type"] == "creative_asset"

    deleted = client.delete(f"/novels/{novel['id']}/creative-assets/{created['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/novels/{novel['id']}/creative-assets", headers=headers).json() == []

    missing = client.delete(f"/novels/{novel['id']}/creative-assets/{created['id']}", headers=headers)
    assert missing.status_code == 404


def test_material_changes_are_recorded_for_user_actions() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Change Novel"}).json()

    created = client.post(
        f"/novels/{novel['id']}/creative-assets",
        headers=headers,
        json={"asset_type": "character", "name": "Jon", "summary": "A sailor."},
    ).json()

    client.patch(
        f"/novels/{novel['id']}/creative-assets/{created['id']}",
        headers=headers,
        json={"summary": "A retired sailor."},
    )
    client.delete(f"/novels/{novel['id']}/creative-assets/{created['id']}", headers=headers)

    changes = client.get(f"/novels/{novel['id']}/material-changes", headers=headers).json()
    assert len(changes) == 3
    assert changes[0]["action"] == "deleted"
    assert changes[0]["actor_source"] == "user"
    assert changes[1]["action"] == "updated"
    assert changes[2]["action"] == "created"
