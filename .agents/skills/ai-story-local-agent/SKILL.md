---
name: ai-story-local-agent
description: Connect a local coding or writing Agent to AI Story through the Go CLI, then use project-local AI Story novel skills for platform-grounded writing and revision.
---

# AI Story Local Agent

Use this skill when the user wants you to write, revise, inspect, score-adjacent, or organize a novel with AI Story platform data.

## Setup

The user should provide:

- `AI_STORY_API_BASE`: the running AI Story backend URL.
- `AI_STORY_ACCESS_TOKEN`: the user's current access token.
- The `ai-story` Go CLI binary built from this repository.

Export connection values before running CLI commands:

```bash
export AI_STORY_API_BASE="<backend-url>"
export AI_STORY_ACCESS_TOKEN="<access-token>"
```

## Discover Capabilities

Start by reading the local capability manifest:

```bash
ai-story agent manifest
```

Use the manifest to find HTTP routes and Agent runtime tools.

## Project Skill Pack

This project installs AI Story skills under `.agents/skills/`. The local skill pack includes this core connection skill plus the novel atomic and flow skills:

- `ai-story-scoring` for platform rubric scoring and low-quality risk checks.
- `ai-story-novel-workflow` for routing multi-step novel work.
- `ai-story-novel-chapter-repair` for existing chapter repair.
- `ai-story-novel-new-chapter` for planning and drafting new chapters.
- `ai-story-novel-character-entrance` for heroine, appearance, clothing, first impressions, and relationship tension.
- `ai-story-novel-continuity` for platform truth, timeline, character knowledge, power levels, and material drift.
- Topic, outline, character management, worldbuilding, plot structure, reader promise, prose polish, finalize, market radar, new book start, pre-publish check, and volume review skills for their matching tasks.

When a user asks for novel work, trigger the most specific project skill first. Use `ai-story-novel-workflow` when the task spans multiple skills or needs orchestration.

## Local Agent Orchestration

This skill is the 本地总控层 / Top-Level Controller for AI Story work. It is the task router before any scoring, writing, repair, or material-sync skill runs. `ai-story-novel-workflow 是小说域路由`; use it inside novel work, but keep this local-agent skill responsible for platform connection, capability discovery, task classification, and final state reconciliation.

Task router:

- Platform setup or capability question: read `ai-story agent manifest`, then inspect routes and tools.
- Scoring, audit, platform risk, or ranking: use `ai-story-scoring`.
- Multi-step novel work: use `ai-story-novel-workflow`, then execute the selected flow sequence.
- Existing chapter repair: route to `ai-story-novel-chapter-repair`; follow platform read, Issue Classification, Repair Depth, Sub-Skill Routing, patch, and sync. do not skip straight to prose.
- New chapter: route to `ai-story-novel-new-chapter`; follow platform read, task card, Preflight Gates, Draft Sequence, and Post-Write Sync. do not skip straight to prose.
- Single narrow issue: route directly to the matching atomic skill, such as `ai-story-novel-character-entrance`, `ai-story-novel-continuity`, `ai-story-novel-reader-promise`, or `ai-story-novel-prose-polish`.

## Reuse Story Context

Read materials, timeline events, memories, relationships, and chapter content before writing:

```bash
ai-story api request GET /novels/{novel_id}/creative-assets
ai-story api request GET /novels/{novel_id}/timeline-events
ai-story api request GET /novels/{novel_id}/memory-items
ai-story api request GET /novels/{novel_id}/character-states
ai-story api request GET /novels/{novel_id}/character-attributes
ai-story api request GET /novels/{novel_id}/inventory-items
ai-story api request GET /novels/{novel_id}/map-locations
ai-story api request GET /novels/{novel_id}/relationship-edges
ai-story tools run {novel_id} search_documents_by_keyword --arg query=关键词
```

Before drafting, actively gather context with available routes and tools:

- Materials and worldbuilding: `list_creative_assets`, `/novels/{novel_id}/creative-assets`.
- Timeline: `list_timeline_events`, `/novels/{novel_id}/timeline-events`.
- Character state: `list_character_states`, `/novels/{novel_id}/character-states`.
- Character attributes: `list_character_attributes`, `/novels/{novel_id}/character-attributes`.
- Inventory and quantities: `list_inventory_items`, `/novels/{novel_id}/inventory-items`.
- Map and locations: `list_map_locations`, `/novels/{novel_id}/map-locations`.
- Relationships: `/novels/{novel_id}/relationship-edges`.
- Memory: `list_memory_items`, `search_memory`, `/novels/{novel_id}/memory-items`.
- Existing prose: `read_document`, `search_documents_by_keyword`, `/novels/{novel_id}/search`.
- Semantic references: `search_rag`, `/novels/{novel_id}/rag/search`.
- Recent material edits: `list_material_changes`, `/novels/{novel_id}/material-changes`.

## Local Cache

Use `.store/<小说名>/` for local working caches before editing or writing:

- Save chapter snapshots, downloaded materials, timeline events, memories, and draft notes there.
- Prefer one file per chapter or material group so changes are easy to inspect and recover.
- Treat files under `.store/<小说名>/` as disposable local cache, not as the platform source of truth.

## Novel Quality Guardrails

When writing or revising long-form web fiction, avoid content that severely harms reader experience, including but not limited to:

- AI粗制滥造：滥用AI工具批量生成，严重缺乏原创性，属于“粗制滥造”范畴的。
- 格式混乱：分章异常、标点符号严重错乱、排版格式错乱、短篇童话/公文报告等非长网文体裁等。
- 结构失常：梗概式写文，复述剧情提纲；开篇结尾句式重复堆砌，模板化拼接等。
- 空洞水文：机械罗列时间、动作、对话等流水账式叙事，单调冗长；行文空泛，节奏拖沓，长篇幅无实质情节推进；大量堆砌艰涩难懂的高级概念，无可读性等。

## Workspace Structure Changes

Separate structure edits from prose edits:

- Use `PATCH /novels/{novel_id}/nodes/reorder` only to reorder workspace nodes or chapter tree items.
- Reordering nodes must not change document body text, chapter prose, memories, materials, or timeline content.
- Read the current tree first with `GET /novels/{novel_id}/nodes`, then send reordered node IDs through the CLI/API.
- Use document tools such as `write_document_content` or `propose_document_update` only when the user explicitly asks to change prose.

## Write Through Platform Tools

Create or update story content through Agent tools so AI Story keeps its workspace state:

```bash
ai-story tools run {novel_id} create_chapter_with_content --arg title=章节名 --arg content=正文
ai-story tools run {novel_id} save_key_memory --arg title=记忆标题 --arg body=记忆内容
ai-story tools run {novel_id} create_timeline_event --arg title=事件 --arg event_time=时间 --arg summary=摘要
ai-story tools run {novel_id} upsert_character_attribute --arg character_name=角色名 --arg attribute_key=level --json-arg value=3 --arg unit=级
ai-story tools run {novel_id} upsert_inventory_item --arg owner_name=角色名 --arg item_name=灵石 --json-arg quantity=12 --arg unit=枚
ai-story tools run {novel_id} upsert_map_location --arg name=地点名 --arg location_type=town --arg summary=地点摘要
```

After changing prose, reconcile story state before finishing. Do not finish after prose only:

- Update or create materials when new characters, locations, items, factions, or world rules appear: `list_creative_assets`, `create_character_asset`, `create_world_rule`, `update_creative_asset`.
- Save durable facts, decisions, or continuity constraints as memory: `save_key_memory`; check existing memory with `list_memory_items` or `search_memory` first.
- Update character status after meaningful emotional, physical, goal, location, or secret changes: `list_character_states`, `update_character_state`.
- Update calculable character attributes after level, attribute, resource, location, or numeric changes: `list_character_attributes`, `upsert_character_attribute`, `delete_character_attribute`.
- Update inventory when items, quantities, owners, or storage locations change: `list_inventory_items`, `upsert_inventory_item`, `delete_inventory_item`.
- Update map data when new locations, parent regions, coordinates, or adjacency appear: `list_map_locations`, `upsert_map_location`, `delete_map_location`.
- Update relationships when alliances, conflicts, trust, obligations, or revelations change: `/novels/{novel_id}/relationship-edges`, `create_relationship_edge`, `update_relationship_edge`, `delete_relationship_edge`.
- Update timeline when a scene adds, reorders, reveals, or retcons events: `list_timeline_events`, `create_timeline_event`, `update_timeline_event`, `reorder_timeline_events`.
- If the new prose adds no durable fact changes, state that no material, memory, relationship, or timeline update is needed.

Never write directly to the database. Use the CLI and platform APIs.
