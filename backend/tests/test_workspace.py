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


def test_update_novel_default_model_profile() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="novel-profile@example.com", username="novelprofile")

    novel = client.post("/novels", headers=headers, json={"title": "Profile Book"}).json()
    profile = client.post(
        "/model-profiles",
        headers=headers,
        json={
            "name": "Local Vectors",
            "provider_kind": "openai",
            "api_key": "sk-default",
            "chat_model": "gpt-4o",
            "writing_model": "gpt-4o",
            "summary_model": "gpt-4o-mini",
            "embedding_provider_kind": "ollama",
            "embedding_model": "nomic-embed-text",
            "embedding_base_url": "http://ollama:11434",
        },
    ).json()

    response = client.patch(
        f"/novels/{novel['id']}",
        headers=headers,
        json={"default_model_profile_id": profile["id"]},
    )

    assert response.status_code == 200
    assert response.json()["default_model_profile_id"] == profile["id"]


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


def test_new_workspace_nodes_append_to_the_bottom_of_their_parent() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="append@example.com", username="appenduser")

    novel = client.post("/novels", headers=headers, json={"title": "Append Book"}).json()
    first = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "第一章", "node_type": "chapter", "parent_id": None},
    ).json()
    second = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "第二章", "node_type": "chapter", "parent_id": None},
    ).json()
    folder = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "草稿箱", "node_type": "folder", "parent_id": None},
    ).json()
    draft = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "草稿一", "node_type": "chapter", "parent_id": folder["id"]},
    ).json()

    assert first["position"] == 0
    assert second["position"] == 1
    assert folder["position"] == 2
    assert draft["position"] == 0


def test_update_workspace_node_title_parent_and_position() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="node-update@example.com", username="nodeupdate")

    novel = client.post("/novels", headers=headers, json={"title": "Reorder Book"}).json()
    folder = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Drafts", "node_type": "folder", "parent_id": None},
    ).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()

    response = client.patch(
        f"/novels/{novel['id']}/nodes/{chapter['id']}",
        headers=headers,
        json={"title": "第一章 雾港", "parent_id": folder["id"], "position": 7},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "第一章 雾港"
    assert body["parent_id"] == folder["id"]
    assert body["position"] == 0


def test_bulk_reorder_workspace_nodes_moves_root_item_to_top_and_into_folder() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="bulk-reorder@example.com", username="bulkreorder")

    novel = client.post("/novels", headers=headers, json={"title": "Bulk Reorder Book"}).json()
    folder = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Drafts", "node_type": "folder", "parent_id": None},
    ).json()
    first = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()
    second = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 2", "node_type": "chapter", "parent_id": None},
    ).json()

    response = client.patch(
        f"/novels/{novel['id']}/nodes/reorder",
        headers=headers,
        json={
            "items": [
                {"id": second["id"], "parent_id": None, "position": 0},
                {"id": folder["id"], "parent_id": None, "position": 1},
                {"id": first["id"], "parent_id": folder["id"], "position": 0, "status": "trashed"},
            ]
        },
    )

    assert response.status_code == 200
    nodes = response.json()
    by_id = {node["id"]: node for node in nodes}
    assert by_id[second["id"]]["position"] == 0
    assert by_id[folder["id"]]["position"] == 1
    assert by_id[first["id"]]["parent_id"] == folder["id"]
    assert by_id[first["id"]]["position"] == 0
    assert by_id[first["id"]]["status"] == "trashed"


def test_bulk_reorder_normalizes_omitted_siblings_after_move() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="normalize@example.com", username="normalizeuser")

    novel = client.post("/novels", headers=headers, json={"title": "Normalize Book"}).json()
    first = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "第一章", "node_type": "chapter", "parent_id": None},
    ).json()
    second = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "第二章", "node_type": "chapter", "parent_id": None},
    ).json()
    third = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "第三章", "node_type": "chapter", "parent_id": None},
    ).json()

    response = client.patch(
        f"/novels/{novel['id']}/nodes/reorder",
        headers=headers,
        json={"items": [{"id": third["id"], "parent_id": None, "position": 0}]},
    )

    assert response.status_code == 200
    root_nodes = [node for node in response.json() if node["parent_id"] is None]
    assert [(node["id"], node["position"]) for node in root_nodes] == [
        (third["id"], 0),
        (first["id"], 1),
        (second["id"], 2),
    ]


def test_bulk_reorder_workspace_nodes_rejects_parent_cycles() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="cycle@example.com", username="cycleuser")

    novel = client.post("/novels", headers=headers, json={"title": "Cycle Book"}).json()
    parent = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Parent", "node_type": "folder", "parent_id": None},
    ).json()
    child = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Child", "node_type": "folder", "parent_id": parent["id"]},
    ).json()

    response = client.patch(
        f"/novels/{novel['id']}/nodes/reorder",
        headers=headers,
        json={"items": [{"id": parent["id"], "parent_id": child["id"], "position": 0}]},
    )

    assert response.status_code == 400


def test_import_markdown_novel_creates_chapter_nodes_and_documents() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="import@example.com", username="importuser")

    response = client.post(
        "/novels/import",
        headers=headers,
        json={
            "title": "导入的小说",
            "format": "markdown",
            "content": "# 第一章 雾港\n开场内容。\n\n# 第二章 灯塔\n后续内容。",
        },
    )

    assert response.status_code == 201
    novel = response.json()
    nodes = client.get(f"/novels/{novel['id']}/nodes", headers=headers).json()
    assert [node["title"] for node in nodes] == ["第一章 雾港", "第二章 灯塔"]

    first_document = client.get(f"/documents/{nodes[0]['document_id']}", headers=headers).json()
    assert first_document["content"]["content"][0]["content"][0]["text"] == "开场内容。"


def test_export_novel_as_txt_includes_plain_chapters_in_order() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="export@example.com", username="exportuser")
    novel = client.post("/novels", headers=headers, json={"title": "导出的小说"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "第一章 雾港", "node_type": "chapter", "parent_id": None},
    ).json()
    client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={
            "content": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "开场内容。"}]}],
            }
        },
    )

    response = client.get(f"/novels/{novel['id']}/export?format=txt", headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "第一章 雾港" in response.text
    assert "# 第一章 雾港" not in response.text
    assert "开场内容。" in response.text


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
