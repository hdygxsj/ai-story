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
