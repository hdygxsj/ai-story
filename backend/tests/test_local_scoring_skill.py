from fastapi.testclient import TestClient

from app.main import app


def test_local_scoring_skill_download_contains_rubric_workflow() -> None:
    client = TestClient(app)

    response = client.get("/local-scoring-skill/SKILL.md")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "name: ai-story-scoring" in response.text
    assert "score_chapters_with_rubric" in response.text
    assert "AI粗制滥造" in response.text
    assert "格式混乱" in response.text
    assert "结构失常" in response.text
    assert "空洞水文" in response.text
    assert "ai-story agent manifest" in response.text
    assert "ai-story tools run {novel_id} score_chapters_with_rubric" in response.text
    assert "人物魅力与关系张力" in response.text
    assert "冲突压迫与风险" in response.text
    assert "情绪代价与选择后果" in response.text
    assert "爽点兑现与期待满足" in response.text
    assert "节奏趣味与阅读愉悦" in response.text
    assert "幽默感与互动趣味" not in response.text
    assert "Do not use fixed character names" in response.text
    assert "current novel platform character data" in response.text
    assert "叶尘" not in response.text
    assert "苏念" not in response.text
    assert "江若溪" not in response.text
