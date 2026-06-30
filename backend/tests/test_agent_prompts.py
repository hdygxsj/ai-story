from uuid import uuid4

from app.agent.atomic_ops import ATOMIC_OPS_GUIDANCE
from app.agent.prompts import append_agent_runtime_guidance


def test_append_agent_runtime_guidance_includes_atomic_ops() -> None:
    novel_id = uuid4()
    document_id = uuid4()
    prompt = append_agent_runtime_guidance(
        "base prompt",
        novel_id=novel_id,
        document_id=document_id,
    )

    assert "base prompt" in prompt
    assert ATOMIC_OPS_GUIDANCE.strip() in prompt
    assert "calculate" in prompt
    assert "精确计算" in prompt
    assert "write_document_content" in prompt
    assert "split_chapter_by_max_chars" in prompt
    assert str(novel_id) in prompt
    assert str(document_id) in prompt
    assert "不要只在对话里展示" in prompt


def test_append_agent_runtime_guidance_includes_platform_novel_skills() -> None:
    novel_id = uuid4()
    prompt = append_agent_runtime_guidance(
        "base prompt",
        novel_id=novel_id,
        document_id=None,
    )

    assert "平台 Agent 内置小说 skill 路由" in prompt
    assert "ai-story-novel-workflow" in prompt
    assert "ai-story-novel-character-entrance" in prompt
    assert "ai-story-novel-chapter-repair" in prompt
    assert "ai-story-novel-new-chapter" in prompt
    assert "人物登场门槛" in prompt
    assert "主角、女主、反派、关键盟友" in prompt
    assert "至少一个外部可记忆标记" in prompt
    assert "主流程编排" in prompt
    assert "问题分类" in prompt
    assert "修复深度" in prompt
    assert "前置门槛" in prompt
    assert "先读取 AI Story 平台数据" in prompt
    assert ".webnovel" in prompt


def test_append_agent_runtime_guidance_without_open_document() -> None:
    novel_id = uuid4()
    prompt = append_agent_runtime_guidance(
        "base prompt",
        novel_id=novel_id,
        document_id=None,
    )

    assert "split_chapter_by_max_chars" in prompt
    assert "当前打开的文档 ID" not in prompt
