from fastapi.testclient import TestClient

from app.main import app


def test_local_novel_skills_download_atomic_and_flow_skills() -> None:
    client = TestClient(app)

    expected = {
        "ai-story-novel-topic": "Book pitch",
        "ai-story-novel-outline": "Platform outline",
        "ai-story-novel-character-management": "Character state",
        "ai-story-novel-worldbuilding": "World rule",
        "ai-story-novel-plot-structure": "Plot contract",
        "ai-story-novel-reader-promise": "reader promise",
        "ai-story-novel-character-entrance": "Core characters cannot enter naked",
        "ai-story-novel-continuity": "platform truth",
        "ai-story-novel-prose-polish": "Polish pass",
        "ai-story-novel-finalize": "Publish check",
        "ai-story-novel-market-radar": "Platform radar",
        "ai-story-novel-new-book-start": "New book flow",
        "ai-story-novel-chapter-repair": "REQUIRED SUB-SKILL",
        "ai-story-novel-new-chapter": "Chapter task card",
        "ai-story-novel-pre-publish-check": "Pre-publish flow",
        "ai-story-novel-volume-review": "Volume review",
        "ai-story-novel-workflow": "Workflow router",
    }

    for skill_name, required_text in expected.items():
        response = client.get(f"/local-novel-skills/{skill_name}/SKILL.md")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert f"name: {skill_name}" in response.text
        assert required_text in response.text
        assert "AI Story" in response.text
        assert "ai-story agent manifest" in response.text
        assert "platform" in response.text.lower()
        assert ".webnovel" not in response.text


def test_unknown_local_novel_skill_returns_404() -> None:
    client = TestClient(app)

    response = client.get("/local-novel-skills/not-a-skill/SKILL.md")

    assert response.status_code == 404


def test_local_novel_skills_list_exposes_names_and_download_paths() -> None:
    client = TestClient(app)

    response = client.get("/local-novel-skills")

    assert response.status_code == 200
    payload = response.json()
    names = {item["name"] for item in payload["skills"]}
    assert names == {
        "ai-story-novel-topic",
        "ai-story-novel-outline",
        "ai-story-novel-character-management",
        "ai-story-novel-worldbuilding",
        "ai-story-novel-plot-structure",
        "ai-story-novel-reader-promise",
        "ai-story-novel-character-entrance",
        "ai-story-novel-continuity",
        "ai-story-novel-prose-polish",
        "ai-story-novel-finalize",
        "ai-story-novel-market-radar",
        "ai-story-novel-new-book-start",
        "ai-story-novel-chapter-repair",
        "ai-story-novel-new-chapter",
        "ai-story-novel-pre-publish-check",
        "ai-story-novel-volume-review",
        "ai-story-novel-workflow",
    }
    assert (
        "/local-novel-skills/ai-story-novel-chapter-repair/SKILL.md"
        in {item["path"] for item in payload["skills"]}
    )


def test_new_chapter_and_repair_skills_require_character_presence_gate() -> None:
    client = TestClient(app)

    for skill_name in ("ai-story-novel-new-chapter", "ai-story-novel-chapter-repair"):
        response = client.get(f"/local-novel-skills/{skill_name}/SKILL.md")

        assert response.status_code == 200
        assert "Character Presence Gate" in response.text
        assert "主角、女主、反派、关键盟友" in response.text
        assert "至少一个外部可记忆标记" in response.text
        assert "ai-story-novel-character-entrance" in response.text


def test_main_flow_skills_orchestrate_problem_classification_and_subskills() -> None:
    client = TestClient(app)

    repair = client.get("/local-novel-skills/ai-story-novel-chapter-repair/SKILL.md")
    new_chapter = client.get("/local-novel-skills/ai-story-novel-new-chapter/SKILL.md")

    assert repair.status_code == 200
    assert "## Repair Orchestration" in repair.text
    assert "Issue Classification" in repair.text
    assert "Repair Depth" in repair.text
    assert "Sub-Skill Routing" in repair.text
    assert "reader promise" in repair.text
    assert "character entrance" in repair.text
    assert "continuity" in repair.text
    assert "prose polish" in repair.text

    assert new_chapter.status_code == 200
    assert "## New Chapter Orchestration" in new_chapter.text
    assert "Preflight Gates" in new_chapter.text
    assert "Draft Sequence" in new_chapter.text
    assert "Post-Write Sync" in new_chapter.text
    assert "reader promise gate" in new_chapter.text
    assert "character presence gate" in new_chapter.text
    assert "continuity gate" in new_chapter.text


def test_workflow_skill_keeps_flow_sequence_visible() -> None:
    client = TestClient(app)

    response = client.get("/local-novel-skills/ai-story-novel-workflow/SKILL.md")

    assert response.status_code == 200
    assert "## Flow Discipline" in response.text
    assert "repair flow sequence" in response.text
    assert "new chapter flow sequence" in response.text
    assert "do not skip straight to prose" in response.text
