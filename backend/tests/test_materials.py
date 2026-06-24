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


def test_create_relationship_edge_deduplicates_same_pair_and_type() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Relationship Novel"}).json()
    payload = {
        "source_character": "Mira",
        "target_character": "Jon",
        "relationship_type": "allies",
        "description": "They trust each other.",
    }

    first = client.post(f"/novels/{novel['id']}/relationship-edges", headers=headers, json=payload)
    second = client.post(f"/novels/{novel['id']}/relationship-edges", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get(f"/novels/{novel['id']}/relationship-edges", headers=headers).json()) == 1


def test_create_character_state_deduplicates_same_character_and_scope() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Character State Novel"}).json()
    payload = {
        "character_name": "叶尘",
        "state": "【开局状态】F级0星，华夏高三学生",
        "scope": "current",
    }

    first = client.post(f"/novels/{novel['id']}/character-states", headers=headers, json=payload)
    second = client.post(f"/novels/{novel['id']}/character-states", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get(f"/novels/{novel['id']}/character-states", headers=headers).json()) == 1


def test_create_character_state_updates_existing_scope_snapshot() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Character State Novel"}).json()

    created = client.post(
        f"/novels/{novel['id']}/character-states",
        headers=headers,
        json={"character_name": "叶尘", "state": "【开局状态】", "scope": "current"},
    ).json()
    updated = client.post(
        f"/novels/{novel['id']}/character-states",
        headers=headers,
        json={"character_name": "叶尘", "state": "【第三章末】等级提升", "scope": "current"},
    ).json()

    assert created["id"] == updated["id"]
    listed = client.get(f"/novels/{novel['id']}/character-states", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["state"] == "【第三章末】等级提升"


def test_create_timeline_event_deduplicates_same_title_and_event_time() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Timeline Novel"}).json()
    payload = {
        "title": "第二卷：世界大变（成长期）",
        "event_time": "第一卷结束后",
        "summary": "异界之门开启，叶尘成为先行者。",
    }

    first = client.post(f"/novels/{novel['id']}/timeline-events", headers=headers, json=payload)
    second = client.post(f"/novels/{novel['id']}/timeline-events", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert len(client.get(f"/novels/{novel['id']}/timeline-events", headers=headers).json()) == 1


def test_list_timeline_events_sorts_by_volume_order() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Timeline Novel"}).json()

    client.post(
        f"/novels/{novel['id']}/timeline-events",
        headers=headers,
        json={
            "title": "第三卷：开宗立派（崛起期）",
            "event_time": "第二卷结束后",
            "summary": "白墨开宗立派。",
        },
    )
    client.post(
        f"/novels/{novel['id']}/timeline-events",
        headers=headers,
        json={
            "title": "第一卷：觉醒前夜（新手期）",
            "event_time": "故事开始",
            "summary": "叶尘觉醒系统。",
        },
    )
    client.post(
        f"/novels/{novel['id']}/timeline-events",
        headers=headers,
        json={
            "title": "第二卷：世界大变（成长期）",
            "event_time": "第一卷结束后",
            "summary": "异界之门开启。",
        },
    )

    titles = [item["title"] for item in client.get(f"/novels/{novel['id']}/timeline-events", headers=headers).json()]
    assert titles == [
        "第一卷：觉醒前夜（新手期）",
        "第二卷：世界大变（成长期）",
        "第三卷：开宗立派（崛起期）",
    ]


def test_reorder_timeline_events_sets_explicit_display_order() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Reorder Timeline"}).json()

    third = client.post(
        f"/novels/{novel['id']}/timeline-events",
        headers=headers,
        json={"title": "第三卷", "event_time": "后期", "summary": "结局。"},
    ).json()
    first = client.post(
        f"/novels/{novel['id']}/timeline-events",
        headers=headers,
        json={"title": "第一卷", "event_time": "开篇", "summary": "起点。"},
    ).json()
    second = client.post(
        f"/novels/{novel['id']}/timeline-events",
        headers=headers,
        json={"title": "第二卷", "event_time": "中期", "summary": "发展。"},
    ).json()

    response = client.post(
        f"/novels/{novel['id']}/timeline-events/reorder",
        headers=headers,
        json={"event_ids": [third["id"], first["id"], second["id"]]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["title"] for item in payload] == ["第三卷", "第一卷", "第二卷"]
    assert [item["position"] for item in payload] == [1, 2, 3]


def test_structured_story_state_routes_upsert_list_update_and_delete() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Structured State Novel"}).json()

    attribute = client.post(
        f"/novels/{novel['id']}/character-attributes",
        headers=headers,
        json={
            "character_name": "叶尘",
            "attribute_key": "level",
            "value": 3,
            "unit": "级",
            "scope": "current",
            "metadata": {"source": "chapter_3"},
        },
    )
    assert attribute.status_code == 201
    assert attribute.json()["value"] == 3

    updated_attribute = client.post(
        f"/novels/{novel['id']}/character-attributes",
        headers=headers,
        json={
            "character_name": "叶尘",
            "attribute_key": "level",
            "value": 4,
            "unit": "级",
            "scope": "current",
        },
    )
    assert updated_attribute.status_code == 201
    assert updated_attribute.json()["id"] == attribute.json()["id"]
    assert client.get(f"/novels/{novel['id']}/character-attributes", headers=headers).json()[0]["value"] == 4

    inventory_item = client.post(
        f"/novels/{novel['id']}/inventory-items",
        headers=headers,
        json={
            "owner_name": "叶尘",
            "item_name": "灵石",
            "quantity": 12.5,
            "unit": "枚",
            "location_name": "青石镇",
            "description": "战利品",
        },
    )
    assert inventory_item.status_code == 201
    assert inventory_item.json()["quantity"] == 12.5

    patched_item = client.patch(
        f"/novels/{novel['id']}/inventory-items/{inventory_item.json()['id']}",
        headers=headers,
        json={"quantity": 10, "description": "修炼消耗后剩余"},
    )
    assert patched_item.status_code == 200
    assert patched_item.json()["quantity"] == 10
    assert client.get(f"/novels/{novel['id']}/inventory-items", headers=headers).json()[0]["description"] == "修炼消耗后剩余"

    location = client.post(
        f"/novels/{novel['id']}/map-locations",
        headers=headers,
        json={
            "name": "青石镇",
            "location_type": "town",
            "summary": "叶尘觉醒前居住的小镇。",
            "parent_name": "东荒",
            "coordinates": {"x": 12, "y": -3},
            "adjacent_location_names": ["黑风岭"],
        },
    )
    assert location.status_code == 201
    assert location.json()["coordinates"] == {"x": 12, "y": -3}

    assert client.delete(
        f"/novels/{novel['id']}/character-attributes/{attribute.json()['id']}",
        headers=headers,
    ).status_code == 204
    assert client.delete(
        f"/novels/{novel['id']}/inventory-items/{inventory_item.json()['id']}",
        headers=headers,
    ).status_code == 204
    assert client.delete(
        f"/novels/{novel['id']}/map-locations/{location.json()['id']}",
        headers=headers,
    ).status_code == 204

    changes = client.get(f"/novels/{novel['id']}/material-changes", headers=headers).json()
    material_types = {change["material_type"] for change in changes}
    assert {"character_attribute", "inventory_item", "map_location"}.issubset(material_types)
