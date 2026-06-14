from fastapi.testclient import TestClient

from app.main import app
from tests.test_review_flows import auth_headers


def test_confirmation_history_lists_resolved_items() -> None:
    client = TestClient(app)
    headers = auth_headers(client, "history@example.com")
    novel = client.post("/novels", headers=headers, json={"title": "History Novel"}).json()
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

    approved = client.post(f"/confirmations/{confirmation['id']}/approve", headers=headers)
    pending = client.get(f"/novels/{novel['id']}/confirmations", headers=headers)
    history = client.get(f"/novels/{novel['id']}/confirmations/history", headers=headers)

    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert pending.status_code == 200
    assert pending.json() == []
    assert history.status_code == 200
    assert len(history.json()) == 1
    assert history.json()[0]["id"] == confirmation["id"]
    assert history.json()[0]["status"] == "approved"
    assert history.json()[0]["chapter_title"] == "Chapter 1"
    assert history.json()[0]["resolved_at"] is not None
