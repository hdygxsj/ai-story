from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(tags=["local-scoring-skill"])

LOCAL_SCORING_SKILL = """---
name: ai-story-scoring
description: Use when scoring AI Story novel chapters with the platform rubric and low-quality-content risk checks through the Go CLI.
---

# AI Story Scoring

Use this skill when the user wants you to score, audit, or review novel chapters with AI Story data.

## Setup

The user should provide:

- `AI_STORY_API_BASE`: the running AI Story backend URL.
- `AI_STORY_ACCESS_TOKEN`: the user's current access token.
- The `ai-story` Go CLI binary built from this repository.

Export the connection values before running CLI commands:

```bash
export AI_STORY_API_BASE="<backend-url>"
export AI_STORY_ACCESS_TOKEN="<access-token>"
```

## Discover Capabilities

Start by reading the local capability manifest:

```bash
ai-story agent manifest
```

Use the manifest to confirm the `score_chapters_with_rubric` tool and relevant workspace/document routes are available.

## Score From Platform Data

Prefer platform data over local cache when scoring. Read the workspace first, then score all or selected chapters:

```bash
ai-story api request GET /novels/{novel_id}/nodes
ai-story tools run {novel_id} score_chapters_with_rubric --arg scope=all
ai-story tools run {novel_id} score_chapters_with_rubric --arg scope=selected --json-arg node_ids='["chapter-node-id"]'
```

Use selected scoring when the user asks about one chapter or a specific subset. Use all-chapter scoring when the user asks for the whole novel, publication readiness, platform risk, or a ranking across chapters.

## Rubric

Use the platform scoring output as the source of truth, then explain results with these dimensions:

- 钩子与追读：开篇是否有问题、危机、欲望或悬念；章末是否推动继续阅读。
- 情节推进与因果逻辑：本章是否有不可回退的事件增量，而不是原地解释。
- 人物选择与情绪代价：角色是否有选择、代价、情绪变化和关系压力。
- 冲突爽点与压迫感：对抗是否具体，阻力、风险、反转是否足够清楚。
- 语言质量与原创细节：是否有可感知的动作、场景、细节和非模板化表达。

## Low-Quality Risk Checks

Flag serious reader-experience violations, including but not limited to:

- AI粗制滥造：滥用AI工具批量生成，严重缺乏原创性，属于“粗制滥造”范畴的。
- 格式混乱：分章异常、标点符号严重错乱、排版格式错乱、短篇童话/公文报告等非长网文体裁等。
- 结构失常：梗概式写文，复述剧情提纲；开篇结尾句式重复堆砌，模板化拼接等。
- 空洞水文：机械罗列时间、动作、对话等流水账式叙事，单调冗长；行文空泛，节奏拖沓，长篇幅无实质情节推进；大量堆砌艰涩难懂的高级概念，无可读性等。

## Report Format

When reporting scores:

- Start with overall average score, chapter count, and high-risk chapters.
- For each chapter, include total score, platform risk, strongest issue, and one concrete revision suggestion.
- Do not claim freshness unless the score came from live platform CLI/API data in this run.
- If local files conflict with platform content, trust platform content and mention the conflict.
"""


@router.get("/local-scoring-skill/SKILL.md")
async def download_local_scoring_skill() -> Response:
    return Response(LOCAL_SCORING_SKILL, media_type="text/markdown; charset=utf-8")
