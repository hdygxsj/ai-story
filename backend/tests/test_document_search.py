from fastapi.testclient import TestClient

from app.main import app


def auth_headers(
    client: TestClient,
    *,
    email: str = "search@example.com",
    username: str = "searchuser",
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


def test_search_novel_documents_across_chapters() -> None:
    client = TestClient(app)
    headers = auth_headers(client)

    novel = client.post("/novels", headers=headers, json={"title": "Search Novel"}).json()
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

    client.patch(
        f"/documents/{first['document_id']}",
        headers=headers,
        json={
            "content": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "灯塔在雾里熄灭。"}]}],
            }
        },
    )
    client.patch(
        f"/documents/{second['document_id']}",
        headers=headers,
        json={
            "content": {
                "type": "doc",
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": "灯塔重新点亮。"}]}],
            }
        },
    )

    response = client.get(f"/novels/{novel['id']}/search", headers=headers, params={"query": "灯塔"})
    assert response.status_code == 200
    hits = response.json()
    assert len(hits) == 2
    assert {hit["node_title"] for hit in hits} == {"第一章", "第二章"}
    assert all(hit["match_source"] == "body" for hit in hits)
    assert all("灯塔" in hit["snippet"] for hit in hits)


def test_search_novel_documents_matches_chapter_title() -> None:
    client = TestClient(app)
    headers = auth_headers(client, email="title-search@example.com", username="titlesearch")

    novel = client.post("/novels", headers=headers, json={"title": "Title Search"}).json()
    client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "终章 灯塔", "node_type": "chapter", "parent_id": None},
    )

    response = client.get(f"/novels/{novel['id']}/search", headers=headers, params={"query": "灯塔"})
    assert response.status_code == 200
    hits = response.json()
    assert len(hits) == 1
    assert hits[0]["match_source"] == "title"
    assert hits[0]["node_title"] == "终章 灯塔"
