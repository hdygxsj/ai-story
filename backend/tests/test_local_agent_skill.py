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
    assert "character-attributes" in response.text
    assert "inventory-items" in response.text
    assert "map-locations" in response.text
    assert "relationship-edges" in response.text
    assert "list_creative_assets" in response.text
    assert "list_timeline_events" in response.text
    assert "list_character_states" in response.text
    assert "list_character_attributes" in response.text
    assert "upsert_character_attribute" in response.text
    assert "list_inventory_items" in response.text
    assert "upsert_inventory_item" in response.text
    assert "list_map_locations" in response.text
    assert "upsert_map_location" in response.text
    assert "search_memory" in response.text
    assert "search_rag" in response.text
    assert "list_material_changes" in response.text
    assert ".store/<小说名>/" in response.text
    assert "disposable local cache" in response.text
    assert "PATCH /novels/{novel_id}/nodes/reorder" in response.text
    assert "must not change document body text" in response.text
    assert "GET /novels/{novel_id}/nodes" in response.text
    assert "After changing prose" in response.text
    assert "Do not finish after prose only" in response.text
    assert "AI粗制滥造" in response.text
    assert "格式混乱" in response.text
    assert "结构失常" in response.text
    assert "空洞水文" in response.text
    assert "update_character_state" in response.text
    assert "update_relationship_edge" in response.text
    assert "reorder_timeline_events" in response.text
