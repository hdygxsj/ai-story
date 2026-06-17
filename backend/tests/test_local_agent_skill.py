from fastapi.testclient import TestClient

from app.main import app


def test_local_agent_skill_download_contains_cli_workflow() -> None:
    client = TestClient(app)

    response = client.get("/local-agent-skill/SKILL.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "ai-story agent manifest" in response.text
    assert "AI_STORY_ACCESS_TOKEN" in response.text
    assert "creative-assets" in response.text
    assert "timeline-events" in response.text
    assert "character-states" in response.text
    assert "relationship-edges" in response.text
    assert "list_creative_assets" in response.text
    assert "list_timeline_events" in response.text
    assert "list_character_states" in response.text
    assert "search_memory" in response.text
    assert "search_rag" in response.text
    assert "list_material_changes" in response.text
    assert ".store/<小说名>/" in response.text
    assert "disposable local cache" in response.text
