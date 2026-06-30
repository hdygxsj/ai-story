---
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

## AI Reading Requirement

Treat `score_chapters_with_rubric` as a rule-based reference signal, not as the final literary judgment. Before giving a score report or revision priority, the AI agent must read the relevant platform chapter text and, when needed, adjacent chapters or platform materials. Use the tool output to find likely risk points, then explain which conclusions come from the rule score and which come from AI reading.

## Rubric

Use the platform scoring output as a reference baseline, then read the chapter text and explain results with these dimensions:

- 钩子与追读：开篇是否有问题、危机、欲望或悬念；章末是否推动继续阅读。
- 情节推进与因果逻辑：本章是否有不可回退的事件增量，而不是原地解释。
- 人物魅力与关系张力：角色登场、辨识度、主动性和人物关系是否立住。
- 冲突压迫与风险：对抗是否具体，阻力、风险、反转是否足够清楚。
- 情绪代价与选择后果：角色是否有选择、犹豫、牺牲、后悔或关系压力。
- 爽点兑现与期待满足：章节是否兑现胜利、发现、反转、打脸、突破或关键线索。
- 语言质量与原创细节：是否有可感知的动作、场景、细节和非模板化表达。
- 节奏趣味与阅读愉悦：信息密度、轻松互动、反差、吐槽或段落节奏是否让阅读顺畅。

## Character Recognition

Do not use fixed character names or examples when judging the 人物魅力与关系张力 dimension. Use current novel platform character data first: character assets, character states, character attributes, relationship edges, and inventory owners. Then compare that with the actual chapter text. If platform character data is missing, rely on the scoring tool's text-based fallback and say the result depends on incomplete platform character records.

## Low-Quality Risk Checks

Flag serious reader-experience violations, including but not limited to:

- AI粗制滥造：滥用AI工具批量生成，严重缺乏原创性，属于“粗制滥造”范畴的。
- 格式混乱：分章异常、标点符号严重错乱、排版格式错乱、短篇童话/公文报告等非长网文体裁等。
- 结构失常：梗概式写文，复述剧情提纲；开篇结尾句式重复堆砌，模板化拼接等。
- 空洞水文：机械罗列时间、动作、对话等流水账式叙事，单调冗长；行文空泛，节奏拖沓，长篇幅无实质情节推进；大量堆砌艰涩难懂的高级概念，无可读性等。

## Report Format

When reporting scores:

- Start with overall average score, chapter count, and high-risk chapters.
- State that the numeric score and platform risk are rule-based references unless a separate AI/model scoring tool was used.
- For each chapter, include total score, platform risk, strongest issue from AI reading, and one concrete revision suggestion.
- Do not claim freshness unless both the rule score and chapter reading came from live platform CLI/API data in this run.
- If local files conflict with platform content, trust platform content and mention the conflict.
