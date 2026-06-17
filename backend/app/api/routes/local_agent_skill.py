from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter(tags=["local-agent-skill"])

LOCAL_AGENT_SKILL = """---
name: ai-story-local-agent
description: Connect a local coding or writing Agent to AI Story through the Go CLI.
---

# AI Story Local Agent

Use this skill when the user wants you to write or revise a novel with AI Story data.

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

Use the manifest to find HTTP routes and Agent runtime tools.

## Reuse Story Context

Read materials, timeline events, memories, relationships, and chapter content before writing:

```bash
ai-story api request GET /novels/{novel_id}/creative-assets
ai-story api request GET /novels/{novel_id}/timeline-events
ai-story api request GET /novels/{novel_id}/memory-items
ai-story api request GET /novels/{novel_id}/character-states
ai-story api request GET /novels/{novel_id}/relationship-edges
ai-story tools run {novel_id} search_documents_by_keyword --arg query=关键词
```

Before drafting, actively gather context with the available routes and tools:

- Materials and worldbuilding: `list_creative_assets`, `/novels/{novel_id}/creative-assets`.
- Timeline: `list_timeline_events`, `/novels/{novel_id}/timeline-events`.
- Character state: `list_character_states`, `/novels/{novel_id}/character-states`.
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

## Write Through Platform Tools

Create or update story content through Agent tools so AI Story keeps its workspace state:

```bash
ai-story tools run {novel_id} create_chapter_with_content --arg title=章节名 --arg content=正文
ai-story tools run {novel_id} save_key_memory --arg title=记忆标题 --arg body=记忆内容
ai-story tools run {novel_id} create_timeline_event --arg title=事件 --arg event_time=时间 --arg summary=摘要
```

Never write directly to the database. Use the CLI and platform APIs.
"""


@router.get("/local-agent-skill/SKILL.md")
async def download_local_agent_skill() -> Response:
    return Response(LOCAL_AGENT_SKILL, media_type="text/markdown; charset=utf-8")
