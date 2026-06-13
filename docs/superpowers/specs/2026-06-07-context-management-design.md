# Context Management Design

Date: 2026-06-07

## Overview

Add long-term context management to the AI novel workspace: multi-thread Agent conversations per novel, novel-level context source settings, full context assembly from existing memory/RAG/document data, automatic compression at token thresholds, and a context budget UI in the Agent panel.

This spec extends [Agent Novel Platform Design](./2026-06-02-agent-novel-platform-design.md). It does not replace the original Context Manager section; it specifies how to implement it on top of the current MVP codebase.

## Confirmed Product Decisions

| Decision | Choice |
|----------|--------|
| Conversation model | **Multi-thread** — each novel supports multiple conversation topics |
| Context source toggles | **Novel-level** — one settings profile shared by all threads in a novel |
| Compression behavior | **Fully automatic** — compress at 85%, generate snapshot at 95%, continue without pausing |

## Goals

- Persist Agent chat history per conversation; survive page refresh and navigation.
- Load real creative context (document, memories, materials, neighboring chapters, RAG, history) before every Agent run.
- Show context usage and included sources in the Agent panel.
- Automatically compress low-priority context before hitting model limits.
- Let users configure which context sources are enabled per novel.

## Non-Goals (This Phase)

- LangGraph Postgres checkpoint persistence (deferred to a later phase).
- Milvus migration from Postgres RAG (existing Postgres cosine search remains).
- Per-conversation context source overrides.
- User-prompted compression dialogs at thresholds.
- Full assistant-ui plan/tool-call visualization.

## Architecture

### Recommended Approach: Postgres Messages + Context Assembly Service

Use Postgres tables for conversations and messages (UI-friendly, queryable). Add a shared `context_assembly` service called by both sync and stream Agent paths. Defer LangGraph checkpoint integration until message persistence and assembly are stable.

**Rejected alternatives:**

- **Checkpoint-only persistence** — poor fit for conversation list and message browsing UI.
- **Hybrid messages + checkpoints in v1** — unnecessary complexity before the baseline works.

### Data Model

#### `conversations`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `novel_id` | UUID FK → novels | CASCADE delete |
| `user_id` | UUID FK → users | Owner |
| `title` | string(200) | Default: first user message truncated to 30 chars |
| `created_at` | timestamptz | |
| `updated_at` | timestamptz | Bumped on new messages |

Index: `(novel_id, updated_at DESC)`.

#### `messages`

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `conversation_id` | UUID FK → conversations | CASCADE delete |
| `role` | string(20) | `user`, `assistant`, `tool`, `system` |
| `content` | text | Plain text or markdown |
| `metadata` | JSON | `tool_calls`, `confirmation_id`, `context_pack_id`, etc. |
| `created_at` | timestamptz | |

Index: `(conversation_id, created_at)`.

#### `novel_context_settings`

One row per novel (created on first access with defaults).

| Column | Type | Notes |
|--------|------|-------|
| `novel_id` | UUID PK FK → novels | |
| `sources` | JSON | Boolean toggles per source |
| `budget` | JSON | Token limits and counts |
| `updated_at` | timestamptz | |

Default `sources`:

```json
{
  "current_document": true,
  "selected_text": true,
  "key_memories": true,
  "structured_assets": true,
  "neighboring_chapters": true,
  "rag_search": true,
  "conversation_history": true
}
```

Default `budget`:

```json
{
  "max_context_tokens": 8000,
  "response_reserve": 1000,
  "recent_chapters_count": 3,
  "conversation_history_limit": 20
}
```

`max_context_tokens` defaults from the novel's active `ModelProfile.context_window` when available.

#### `context_snapshots`

Created automatically at ≥95% usage.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `novel_id` | UUID FK | |
| `conversation_id` | UUID FK | |
| `summary` | text | Compressed session state |
| `facts` | JSON | Confirmed facts, open questions, decisions |
| `created_at` | timestamptz | |

Also written to `memory_items` with `memory_type=context_snapshot` and indexed in RAG.

#### `context_packs` (debug / inspect)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `conversation_id` | UUID FK | |
| `message_id` | UUID FK nullable | Triggering user message |
| `items` | JSON | Selected items with source, tokens, compressed flag |
| `usage_ratio` | float | 0–1 |
| `created_at` | timestamptz | |

### Context Assembly

New service: `backend/app/services/context_assembly.py`.

**Inputs:** `novel_id`, `conversation_id`, `document_id`, `selected_text`, `user_message`, `AsyncSession`.

**Steps:**

1. Load `novel_context_settings` (create defaults if missing).
2. For each enabled source, fetch data:
   - **current_document** — document content as plain text from `documents` via `document_id`
   - **selected_text** — request payload
   - **key_memories** — `memory_items` where `memory_type` in (`key_memory`, `context_snapshot`), ordered by `importance DESC`
   - **structured_assets** — formatted strings from `creative_assets`, `character_states`, `timeline_events`
   - **neighboring_chapters** — last N chapter documents from `workspace_nodes` by position
   - **rag_search** — `search_rag_chunks(session, novel_id, query=user_message)`
   - **conversation_history** — last M `messages` in thread, formatted as dialogue
3. Call `build_context_pack()` with `ContextBudget(max_tokens, response_reserve)`.
4. Apply compression if needed (see below).
5. Persist `context_packs` row.
6. Return `AssembledContext` with `pack`, `context_detail` (structured status), `status_messages` (human-readable, Chinese).

**System prompt:** `_build_agent_system_prompt()` injects all selected pack items grouped by source, not only `selected_text`.

**Multi-turn LLM input:** Recent conversation history is included both in the context pack and as prior `HumanMessage`/`AIMessage` pairs when calling the model (last 10 turns max for the message list, remainder in pack).

### Compression Policy (Automatic)

Priority for **inclusion** (high → low):

1. `user_instruction`
2. `selected_text`
3. `key_memory` (never auto-removed while source enabled)
4. `current_document`
5. `structured_memory`
6. `neighboring_chapter`
7. `rag_result`
8. `conversation_history` (older turns)

**Thresholds:**

| Usage | Action |
|-------|--------|
| < 70% | Normal; status only |
| ≥ 70% | Warning in `context_status` |
| ≥ 85% | Auto-compress: truncate conversation history → truncate RAG → replace neighboring chapter full text with titles + last paragraph |
| ≥ 95% | Generate `context_snapshot`, inject as high-priority `key_memory`-class item, drop lowest-priority items until < 85% |

Compression never disables user-configured sources; it only shortens their content.

### API

#### Conversations

```
GET    /novels/{novel_id}/conversations
POST   /novels/{novel_id}/conversations                 { title? }
GET    /novels/{novel_id}/conversations/{id}
PATCH  /novels/{novel_id}/conversations/{id}          { title }
DELETE /novels/{novel_id}/conversations/{id}
GET    /novels/{novel_id}/conversations/{id}/messages
```

#### Context Settings

```
GET    /novels/{novel_id}/context-settings
PATCH  /novels/{novel_id}/context-settings             { sources?, budget? }
```

#### Agent (extended)

```
POST /novels/{novel_id}/agent/messages
POST /novels/{novel_id}/agent/messages/stream
```

Request adds optional `conversation_id`. If omitted, create a new conversation.

Response adds `context_detail`:

```json
{
  "usage_ratio": 0.62,
  "items": [
    { "source": "key_memory", "tokens": 120, "compressed": false }
  ],
  "warnings": ["上下文占用约 62%"],
  "snapshot_id": null
}
```

`context_status` remains a `list[str]` for backward compatibility (Chinese messages).

### Frontend

#### Agent Panel Layout

```
┌─────────────────┬──────────────────────────────┐
│ + 新对话         │  共创 Agent          就绪   │
│ ─────────────── │  上下文 62%  ████████░░░░    │
│ ● 第三章改写     │  记忆 · RAG · 邻章 · 历史   │
│   人物设定讨论   │  ─────────────────────────  │
│   大纲规划       │  [chat bubbles]              │
│                 │  ─────────────────────────  │
│ ⚙ 上下文设置     │  [Sender]                    │
└─────────────────┴──────────────────────────────┘
```

- **Conversation sidebar** — list, create, switch, rename, delete.
- **Context status bar** — usage progress, source chips, compression/snapshot warnings from `context_detail`.
- **Context settings drawer** — novel-level source toggles and budget fields; opened from sidebar footer.

#### Memory Page Additions

- Tab or section: **已确认记忆** via existing `GET /novels/{id}/memory-items`.
- Show `context_snapshot` entries with distinct styling.

### Agent Runtime Changes

| Module | Change |
|--------|--------|
| `agent.py` | Accept `conversation_id`; persist messages; call assembly |
| `chat_stream.py` | Same assembly path as sync |
| `graph.py` | Real pack in prompt; multi-turn messages |
| `tools.py` | Wire `search_memory`, `search_rag`; handle `draft_key_memory` → review queue |
| `context.py` | Export compression helpers; Chinese status messages |

### Delivery Phases

| Phase | Deliverable | Verification |
|-------|-------------|--------------|
| P1 | Migrations + conversation/message CRUD + Agent persistence | Refresh keeps history |
| P2 | Context assembly from DB + expanded system prompt | Agent cites memories/chapters |
| P3 | 85/95% auto compression + snapshots | Long thread stays under budget |
| P4 | Agent panel sidebar + context bar + settings drawer | Full UI |
| P5 | Memory tools + approved memories on memory page | "记住这个" end-to-end |

### Testing

**Backend:**

- Conversation CRUD authorization (novel ownership).
- Message persistence on stream and sync paths.
- Assembly loads each source when enabled; skips when disabled.
- Compression reduces tokens at 85%; snapshot created at 95%.
- `context_detail` shape in API responses.

**Frontend:**

- Conversation list render and switch.
- History reload on mount.
- Context status bar from `context_detail`.
- Settings drawer save/load.

### Error Handling

- Missing `conversation_id` on send → auto-create conversation.
- Deleted conversation → 404; frontend starts new thread.
- RAG unavailable → continue without RAG items; warn in `context_status`.
- Document not found → skip `current_document`; warn in status.
- Model not configured → existing behavior preserved.

## Related Files

- `backend/app/agent/context.py` — pack algorithm (exists)
- `backend/app/agent/context_loader.py` — thin wrapper (exists, extend or replace)
- `backend/app/services/rag.py` — `search_rag_chunks` (exists)
- `backend/app/api/routes/memory.py` — memory APIs (exists)
- `frontend/src/features/agent/AgentPanel.tsx` — chat UI (exists)
- `frontend/src/api/memory.ts` — `listMemoryItems` (exists, unused in UI)
