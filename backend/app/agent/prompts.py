from uuid import UUID

from app.agent.atomic_ops import ATOMIC_OPS_GUIDANCE
from app.agent.chapter_body import PROSE_BODY_GUIDANCE
from app.agent.tools import MATH_CALCULATION_GUIDANCE


def append_agent_runtime_guidance(
    system_prompt: str,
    *,
    novel_id: UUID,
    document_id: UUID | None,
) -> str:
    lines = [
        system_prompt,
        f"\n\n当前小说 ID: {novel_id}",
        f"\n\n{ATOMIC_OPS_GUIDANCE}",
        f"\n\n{MATH_CALCULATION_GUIDANCE}",
        f"\n\n{PROSE_BODY_GUIDANCE}",
    ]
    if document_id is not None:
        lines.append(f"\n当前打开的文档 ID: {document_id}。")
    return "".join(lines)
