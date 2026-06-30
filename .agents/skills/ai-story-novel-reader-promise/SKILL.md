---
name: ai-story-novel-reader-promise
description: Use when diagnosing web-novel retention, opening funnels, reader promise mismatch, chapter hooks, title-intro alignment, or why readers drop before continuing.
---

# AI Story Novel Reader Promise

Atomic skill for checking whether a chapter gives readers what the title, intro, genre, and first screen promised.

## Setup

Use AI Story through the Go CLI:

```bash
export AI_STORY_API_BASE="<backend-url>"
export AI_STORY_ACCESS_TOKEN="<access-token>"
ai-story agent manifest
```

Prefer platform data over local caches.

## Reader Promise Check

Read platform metadata, nodes, and selected chapter scores:

```bash
ai-story api request GET /novels
ai-story api request GET /novels/{novel_id}/nodes
ai-story tools run {novel_id} score_chapters_with_rubric --arg scope=selected --json-arg node_ids='["chapter-node-id"]'
```

Evaluate title promise, first-screen delivery, chapter purpose, hook chain, explanation load, and reward timing. Distinguish prose quality from promise mismatch: a chapter can be well written and still leak readers if it delays the promised genre payoff.

## Repair Direction

For published chapters, prefer minimal entrance, first-screen, bridge, or hook patches. For drafts, recommend larger structure changes only when the core selling point arrives too late or chapter purpose is missing.
