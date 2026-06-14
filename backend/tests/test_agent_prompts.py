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
    assert "write_document_content" in prompt
    assert "split_chapter_by_max_chars" in prompt
    assert str(novel_id) in prompt
    assert str(document_id) in prompt
    assert "不要只在对话里展示" in prompt


def test_append_agent_runtime_guidance_without_open_document() -> None:
    novel_id = uuid4()
    prompt = append_agent_runtime_guidance(
        "base prompt",
        novel_id=novel_id,
        document_id=None,
    )

    assert "split_chapter_by_max_chars" in prompt
    assert "当前打开的文档 ID" not in prompt
