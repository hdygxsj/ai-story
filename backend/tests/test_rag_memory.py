from fastapi.testclient import TestClient

from app.agent.context import ContextBudget
from app.agent.context_loader import build_agent_context
from app.main import app


def auth_headers(client: TestClient) -> dict[str, str]:
    client.post(
        "/auth/register",
        json={"email": "rag@example.com", "username": "rag", "password": "secret123"},
    )
    token = client.post(
        "/auth/login",
        json={"login": "rag@example.com", "password": "secret123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_document_save_indexes_rag_chunk_for_search() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "RAG Novel"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Chapter 1", "node_type": "chapter", "parent_id": None},
    ).json()
    client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={
            "content": {
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "The lighthouse stores the forbidden map."}],
                    }
                ],
            }
        },
    )

    results = client.get(f"/novels/{novel['id']}/rag/search?query=lighthouse", headers=headers)

    assert results.status_code == 200
    assert results.json()[0]["source_type"] == "document"
    assert "forbidden map" in results.json()[0]["text"]


def test_approved_memory_indexes_rag_chunk_for_search() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Memory RAG Novel"}).json()
    review = client.post(
        f"/novels/{novel['id']}/memory-review-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "Lighthouse vow",
            "body": "The lighthouse vow must never be broken.",
            "importance": 95,
        },
    ).json()
    client.post(f"/memory-review-items/{review['id']}/approve", headers=headers)

    results = client.get(f"/novels/{novel['id']}/rag/search?query=lighthouse vow", headers=headers)

    assert results.status_code == 200
    assert results.json()[0]["source_type"] == "memory"


def test_rag_search_excludes_trashed_document_chunks() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Trashed RAG Novel"}).json()
    chapter = client.post(
        f"/novels/{novel['id']}/nodes",
        headers=headers,
        json={"title": "Discarded", "node_type": "chapter", "parent_id": None},
    ).json()
    client.patch(
        f"/documents/{chapter['document_id']}",
        headers=headers,
        json={
            "content": {
                "type": "doc",
                "content": [
                    {"type": "paragraph", "content": [{"type": "text", "text": "obsolete lighthouse clue"}]}
                ],
            }
        },
    )
    reorder = client.patch(
        f"/novels/{novel['id']}/nodes/reorder",
        headers=headers,
        json={
            "items": [
                {
                    "id": chapter["id"],
                    "parent_id": None,
                    "position": 0,
                    "status": "trashed",
                }
            ]
        },
    )

    assert reorder.status_code == 200
    assert reorder.json()[0]["status"] == "trashed"

    results = client.get(f"/novels/{novel['id']}/rag/search?query=lighthouse", headers=headers)

    assert results.status_code == 200
    assert results.json() == []


def test_context_loader_prioritizes_key_memory_and_rag_results() -> None:
    pack = build_agent_context(
        user_instruction="Continue the scene.",
        current_document_text="The protagonist approaches the harbor.",
        selected_text=None,
        key_memories=["The lighthouse vow must never be broken."],
        structured_assets=["Lighthouse: abandoned signal tower."],
        neighboring_chapters=["Earlier chapter: the crew found a brass key."],
        rag_results=["RAG: the forbidden map is hidden under the lens."],
        budget=ContextBudget(max_tokens=2000, response_tokens=500),
    )

    sources = [item.source for item in pack.items]
    assert "key_memory" in sources
    assert "rag_result" in sources
    assert any("上下文占用" in status for status in pack.status_messages)
