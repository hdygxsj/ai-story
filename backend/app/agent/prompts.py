from uuid import UUID

from app.agent.atomic_ops import ATOMIC_OPS_GUIDANCE
from app.agent.chapter_body import PROSE_BODY_GUIDANCE
from app.agent.tools import MATH_CALCULATION_GUIDANCE

NOVEL_SKILL_GUIDANCE = """平台 Agent 内置小说 skill 路由：
- 总控分流、多步骤写作或修复：ai-story-novel-workflow。
- 新书、选题、标题、简介、卖点：ai-story-novel-topic、ai-story-novel-new-book-start。
- 大纲、卷纲、章节卡、节奏结构：ai-story-novel-outline、ai-story-novel-plot-structure。
- 角色卡、女主登场、颜值、着装、关系张力：ai-story-novel-character-management、ai-story-novel-character-entrance。
- 世界观、地图、道具、组织、规则：ai-story-novel-worldbuilding。
- 已有章节修复、前十章留存、读者承诺、连续性：ai-story-novel-chapter-repair、ai-story-novel-reader-promise、ai-story-novel-continuity。
- 新章节续写、正文润色、发布前检查、整卷复盘：ai-story-novel-new-chapter、ai-story-novel-prose-polish、ai-story-novel-pre-publish-check、ai-story-novel-volume-review。
- 市场风向或包装校准：ai-story-novel-market-radar。

人物登场门槛：新章节、章节修复或段落改写中，只要主角、女主、反派、关键盟友等重要角色首次出现、重新进入本章舞台、承担新关系压力或被读者重新认识，必须同时使用 ai-story-novel-character-entrance。输出或改文前检查角色身份、场景作用、第一印象、行为/语气，以及至少一个外部可记忆标记；不能让重要角色只以名字、功能、对白或剧情位置出现。

主流程编排：使用 ai-story-novel-chapter-repair 时，先读平台章节和相邻上下文，再做问题分类，至少判断读者承诺、人物登场、连续性、结构节奏、语言/AI味、章末钩子和平台风险；随后确定修复深度，已发布章节默认微调，草稿可轻改，只有用户明确要求或草稿严重失效才重写；最后按问题路由 reader-promise、character-entrance、continuity、plot-structure、prose-polish、scoring 等原子 skill。使用 ai-story-novel-new-chapter 时，先建章节任务卡，再过前置门槛：reader promise gate、character presence gate、continuity gate、scene purpose gate，然后写正文，最后同步材料、记忆、时间线、角色状态、关系、地图和物品变化。

这些 skill 是平台 Agent 的内置工作法，不需要外部安装才能使用。处理小说任务时，先读取 AI Story 平台数据、当前章节、材料、时间线、记忆、角色状态、关系和工具结果，再按相应 skill 的流程输出或改文。不要脱离平台另起 `.webnovel`、本地章节缓存或平台外真相；被用户采纳的持久事实必须写回平台材料、记忆、时间线或文档工具。"""


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
        f"\n\n{NOVEL_SKILL_GUIDANCE}",
    ]
    if document_id is not None:
        lines.append(f"\n当前打开的文档 ID: {document_id}。")
    return "".join(lines)
