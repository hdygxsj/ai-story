from uuid import uuid4

from app.agent.prompts import append_agent_runtime_guidance


def test_append_agent_runtime_guidance_includes_document_write_tools() -> None:
    novel_id = uuid4()
    document_id = uuid4()
    prompt = append_agent_runtime_guidance(
        "base prompt",
        novel_id=novel_id,
        document_id=document_id,
    )

    assert "propose_document_update" in prompt
    assert "create_chapter_with_content" in prompt
    assert str(document_id) in prompt
    assert "不要只在回复里展示正文" in prompt


def test_append_agent_runtime_guidance_without_open_document() -> None:
    novel_id = uuid4()
    prompt = append_agent_runtime_guidance(
        "base prompt",
        novel_id=novel_id,
        document_id=None,
    )

    assert "create_chapter_with_content" in prompt
    assert "当前没有打开的文档" in prompt
    assert "禁止只调用 create_workspace_node" in prompt
    assert "禁止用 create_workspace_node" in prompt
    assert "禁止让用户手动" in prompt
    assert "delete_creative_assets" in prompt
