# Context Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement multi-thread Agent conversations, novel-level context settings, full context assembly from DB sources, automatic compression, and context budget UI.

**Architecture:** Postgres tables for `conversations`, `messages`, `novel_context_settings`, `context_snapshots`, `context_packs`. A shared `context_assembly` service feeds both sync and stream Agent paths. Frontend adds a conversation sidebar and context status bar to `AgentPanel`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, Alembic, LangChain messages, React, TypeScript, Ant Design X, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-06-07-context-management-design.md`

---

## File Map

| File | Responsibility |
|------|----------------|
| `backend/alembic/versions/0009_context_management.py` | New tables migration |
| `backend/app/models/conversation.py` | Conversation, Message, NovelContextSettings, ContextSnapshot, ContextPack models |
| `backend/app/schemas/conversation.py` | Request/response schemas |
| `backend/app/schemas/context.py` | ContextDetail, sources/budget schemas |
| `backend/app/services/conversations.py` | CRUD, message persistence, auto-title |
| `backend/app/services/context_settings.py` | Get/create defaults, patch settings |
| `backend/app/services/context_assembly.py` | Load sources, compress, snapshot |
| `backend/app/api/routes/conversations.py` | Conversation + settings routes |
| `backend/app/api/routes/agent.py` | Wire assembly + persistence |
| `backend/app/agent/chat_stream.py` | Use assembly service |
| `backend/app/agent/graph.py` | Multi-turn messages + full prompt |
| `backend/app/agent/context.py` | Chinese status + compression helpers |
| `backend/app/agent/tools.py` | Real search_memory/search_rag |
| `frontend/src/api/conversations.ts` | Conversation + settings API client |
| `frontend/src/features/agent/ConversationSidebar.tsx` | Thread list UI |
| `frontend/src/features/agent/ContextStatusBar.tsx` | Usage bar + source chips |
| `frontend/src/features/agent/ContextSettingsDrawer.tsx` | Novel-level toggles |
| `frontend/src/features/agent/AgentPanel.tsx` | Integrate sidebar + status + history load |
| `frontend/src/features/workspace/WorkspacePage.tsx` | Approved memories section |

---

## Phase P1: Conversations + Message Persistence

### Task 1: Migration and models

**Files:**
- Create: `backend/alembic/versions/0009_context_management.py`
- Create: `backend/app/models/conversation.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write migration `0009_context_management.py`**

```python
"""Add conversations, messages, context settings, snapshots, context packs."""

revision = "0009_context_management"
down_revision = "0008_model_profile_providers"

def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("novel_id", sa.Uuid(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_novel_updated", "conversations", ["novel_id", "updated_at"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_created", "messages", ["conversation_id", "created_at"])

    op.create_table(
        "novel_context_settings",
        sa.Column("novel_id", sa.Uuid(), sa.ForeignKey("novels.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("budget", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "context_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("novel_id", sa.Uuid(), sa.ForeignKey("novels.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "context_packs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("message_id", sa.Uuid(), sa.ForeignKey("messages.id", ondelete="SET NULL"), nullable=True),
        sa.Column("items", sa.JSON(), nullable=False),
        sa.Column("usage_ratio", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
```

- [ ] **Step 2: Create SQLAlchemy models in `conversation.py`**

Follow `MemoryItem` pattern: `Mapped[UUID]`, `mapped_column`, `extra_metadata` mapped to `"metadata"` column for `Message`.

- [ ] **Step 3: Export models from `models/__init__.py`**

- [ ] **Step 4: Run migration in Docker**

```bash
docker compose run --rm api alembic upgrade head
```

Expected: `0009_context_management` applied.

---

### Task 2: Conversation service + tests

**Files:**
- Create: `backend/app/services/conversations.py`
- Create: `backend/app/schemas/conversation.py`
- Create: `backend/tests/test_conversations.py`

- [ ] **Step 1: Write failing test**

```python
def test_create_conversation_and_persist_messages(client, auth_headers, novel):
    created = client.post(
        f"/novels/{novel['id']}/conversations",
        headers=auth_headers,
        json={"title": "第三章改写"},
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    listed = client.get(f"/novels/{novel['id']}/conversations", headers=auth_headers)
    assert listed.json()[0]["title"] == "第三章改写"

    messages = client.get(
        f"/novels/{novel['id']}/conversations/{conversation_id}/messages",
        headers=auth_headers,
    )
    assert messages.json() == []
```

- [ ] **Step 2: Run test — expect FAIL**

```bash
docker compose run --rm api pytest tests/test_conversations.py::test_create_conversation_and_persist_messages -v
```

- [ ] **Step 3: Implement `conversations.py`**

```python
async def create_conversation(session, *, novel_id, user_id, title: str) -> Conversation: ...
async def list_conversations(session, *, novel_id) -> list[Conversation]: ...
async def get_conversation(session, *, novel_id, conversation_id) -> Conversation: ...
async def append_message(session, *, conversation_id, role, content, metadata=None) -> Message: ...
async def list_messages(session, *, conversation_id) -> list[Message]: ...
async def touch_conversation(session, conversation: Conversation) -> None: ...
async def auto_title_from_message(message: str) -> str:
    return message.strip()[:30] or "新对话"
```

- [ ] **Step 4: Implement routes in `conversations.py` router**

Register in `app/api/routes/__init__.py` and `main.py`.

- [ ] **Step 5: Run tests — expect PASS**

---

### Task 3: Wire Agent routes to persist messages

**Files:**
- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/api/routes/agent.py`
- Modify: `backend/app/agent/chat_stream.py`
- Modify: `backend/tests/test_model_runtime.py`

- [ ] **Step 1: Extend `AgentMessageRequest`**

```python
class AgentMessageRequest(BaseModel):
    message: str
    document_id: UUID | None = None
    selected_text: str | None = None
    conversation_id: UUID | None = None
```

- [ ] **Step 2: Write failing test**

```python
def test_agent_stream_persists_messages(client, auth_headers, novel_with_profile, monkeypatch):
    # mock model astream as in existing test
    response = client.post(
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=auth_headers,
        json={"message": "帮我规划下一幕"},
    )
    assert response.status_code == 200
    conversations = client.get(f"/novels/{novel['id']}/conversations", headers=auth_headers).json()
    assert len(conversations) == 1
    messages = client.get(
        f"/novels/{novel['id']}/conversations/{conversations[0]['id']}/messages",
        headers=auth_headers,
    ).json()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
```

- [ ] **Step 3: In `agent.py` stream handler**

Before streaming:
- Resolve or create `conversation_id`
- `append_message(role="user", content=payload.message)`

After `done` event:
- `append_message(role="assistant", content=final_message)`
- Return `conversation_id` in done payload

- [ ] **Step 4: Run test — expect PASS**

---

### Task 4: Frontend conversation API + history load

**Files:**
- Create: `frontend/src/api/conversations.ts`
- Modify: `frontend/src/features/agent/AgentPanel.tsx`
- Create: `frontend/src/features/agent/ConversationSidebar.tsx`
- Modify: `frontend/src/test/workspace.test.tsx`

- [ ] **Step 1: Add API client**

```typescript
export type Conversation = { id: string; title: string; updated_at: string };
export type StoredMessage = { id: string; role: "user" | "assistant"; content: string };

export function listConversations(token: string, novelId: string) { ... }
export function createConversation(token: string, novelId: string, title?: string) { ... }
export function listConversationMessages(token: string, novelId: string, conversationId: string) { ... }
export function deleteConversation(token: string, novelId: string, conversationId: string) { ... }
```

- [ ] **Step 2: `AgentPanel` loads conversations on mount**

- `activeConversationId` state
- On switch: fetch messages, map to `ChatMessage[]`
- On send: pass `conversation_id` to `streamAgentMessage`
- On done: if new `conversation_id` in payload, set active

- [ ] **Step 3: `ConversationSidebar`**

List conversations, highlight active, "+ 新对话" creates empty thread.

- [ ] **Step 4: Update workspace tests** — mock conversation endpoints.

- [ ] **Step 5: Run frontend tests**

```bash
cd frontend && npm test -- --run src/test/workspace.test.tsx
```

---

## Phase P2: Context Assembly

### Task 5: Context settings service + API

**Files:**
- Create: `backend/app/services/context_settings.py`
- Create: `backend/app/schemas/context.py`
- Modify: `backend/app/api/routes/conversations.py`
- Create: `backend/tests/test_context_settings.py`

- [ ] **Step 1: Test defaults created on first GET**

```python
def test_context_settings_defaults(client, auth_headers, novel):
    response = client.get(f"/novels/{novel['id']}/context-settings", headers=auth_headers)
    assert response.status_code == 200
    assert response.json()["sources"]["key_memories"] is True
    assert response.json()["budget"]["recent_chapters_count"] == 3
```

- [ ] **Step 2: Implement `get_or_create_context_settings`**

Default `max_context_tokens` from novel's `default_model_profile.context_window` or 8000.

- [ ] **Step 3: PATCH endpoint**

- [ ] **Step 4: Run tests — PASS**

---

### Task 6: Context assembly service

**Files:**
- Create: `backend/app/services/context_assembly.py`
- Create: `backend/tests/test_context_assembly.py`
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/app/agent/chat_stream.py`

- [ ] **Step 1: Write failing integration test with seeded data**

```python
async def test_assembly_loads_key_memories_and_document(session, novel, document, memory_item):
    result = await assemble_context(
        session,
        novel_id=novel.id,
        conversation_id=conversation.id,
        document_id=document.id,
        selected_text=None,
        user_message="继续写下去",
    )
    sources = {item.source for item in result.pack.items}
    assert "key_memory" in sources
    assert "current_document" in sources
```

- [ ] **Step 2: Implement loaders (private functions in `context_assembly.py`)**

```python
async def _load_document_text(session, document_id) -> str: ...
async def _load_key_memories(session, novel_id) -> list[str]: ...
async def _load_structured_assets(session, novel_id) -> list[str]: ...
async def _load_neighboring_chapters(session, novel_id, document_id, count) -> list[str]: ...
async def _load_rag_results(session, novel_id, query) -> list[str]: ...
async def _load_conversation_history(session, conversation_id, limit) -> list[str]: ...
```

Use existing `search_rag_chunks` from `app/services/rag.py`. For document text, extract plain text from TipTap JSON (add small helper in `services/documents.py` if needed).

- [ ] **Step 3: Implement `assemble_context`**

Respect `novel_context_settings.sources` toggles. Call `build_context_pack`. Return:

```python
@dataclass
class AssembledContext:
    pack: ContextPack
    context_detail: ContextDetail
    status_messages: list[str]
    history_messages: list[BaseMessage]  # for LLM multi-turn
```

- [ ] **Step 4: Update `_build_agent_system_prompt` in `graph.py`**

```python
def _build_agent_system_prompt(pack: ContextPack) -> str:
    sections = {
        "selected_text": "用户当前选中的段落",
        "current_document": "当前文档",
        "key_memory": "关键记忆",
        "structured_memory": "结构化素材",
        "neighboring_chapter": "相邻章节",
        "rag_result": "检索结果",
        "user_instruction": "用户指令",
    }
    lines = ["你是 AI 小说工坊的共创 Agent...", "请使用与用户相同的语言回复。"]
    for item in pack.items:
        if item.source == "user_instruction":
            continue
        label = sections.get(item.source, item.source)
        lines.append(f"【{label}】\n{item.text}")
    return "\n\n".join(lines)
```

- [ ] **Step 5: Wire assembly into `chat_stream.py` and `graph.py`**

Replace empty `build_context_pack` calls. Pass `history_messages` to `model.astream` / `model.invoke`.

- [ ] **Step 6: Run tests — PASS**

---

### Task 7: Structured context_detail in API

**Files:**
- Modify: `backend/app/schemas/agent.py`
- Modify: `backend/app/schemas/context.py`
- Modify: `backend/app/agent/context.py`

- [ ] **Step 1: Add schemas**

```python
class ContextDetailItem(BaseModel):
    source: str
    tokens: int
    compressed: bool = False

class ContextDetail(BaseModel):
    usage_ratio: float
    items: list[ContextDetailItem]
    warnings: list[str]
    snapshot_id: UUID | None = None
```

- [ ] **Step 2: Add `context_detail` to `AgentMessageResponse` and stream `done` event**

- [ ] **Step 3: Translate status messages to Chinese in `context.py`**

```python
status_messages = [f"上下文占用约 {round(usage_ratio * 100)}%。"]
```

- [ ] **Step 4: Test stream response contains `context_detail`**

---

## Phase P3: Auto Compression + Snapshots

### Task 8: Compression helpers

**Files:**
- Modify: `backend/app/agent/context.py`
- Modify: `backend/app/services/context_assembly.py`
- Create: `backend/tests/test_context_compression.py`

- [ ] **Step 1: Test 85% triggers compression**

Seed large conversation history + RAG strings. Assert `compressed=True` on dropped/truncated items.

- [ ] **Step 2: Implement `compress_context_pack(pack, target_ratio=0.85)`**

Apply truncation in priority order (history → rag → neighbors).

- [ ] **Step 3: Test 95% creates snapshot**

```python
def test_snapshot_created_at_95_percent(session, novel, conversation):
    result = await assemble_context(...)  # with oversized inputs
    assert result.context_detail.snapshot_id is not None
    snapshot = await session.get(ContextSnapshot, result.context_detail.snapshot_id)
    assert snapshot.summary
```

- [ ] **Step 4: Implement `_create_context_snapshot`**

Write `context_snapshots` row + `memory_items` with `memory_type=context_snapshot` + `index_text`.

- [ ] **Step 5: Persist `context_packs` row after each assembly**

- [ ] **Step 6: Run tests — PASS**

---

## Phase P4: Context Budget UI

### Task 9: Context status bar

**Files:**
- Create: `frontend/src/features/agent/ContextStatusBar.tsx`
- Modify: `frontend/src/api/agent.ts`
- Modify: `frontend/src/features/agent/AgentPanel.tsx`

- [ ] **Step 1: Extend frontend types**

```typescript
export type ContextDetail = {
  usage_ratio: number;
  items: { source: string; tokens: number; compressed: boolean }[];
  warnings: string[];
  snapshot_id?: string | null;
};
```

- [ ] **Step 2: Build `ContextStatusBar`**

Ant Design `Progress` for `usage_ratio`, `Tag` chips for enabled sources (map source keys to Chinese labels), `Alert` for warnings.

- [ ] **Step 3: Wire `onDone` in `AgentPanel`**

```typescript
const [contextDetail, setContextDetail] = useState<ContextDetail | null>(null);
// in onDone:
setContextDetail(payload.context_detail ?? null);
```

- [ ] **Step 4: Render below Card title / above message scroll**

---

### Task 10: Context settings drawer

**Files:**
- Create: `frontend/src/features/agent/ContextSettingsDrawer.tsx`
- Modify: `frontend/src/api/conversations.ts`
- Modify: `frontend/src/features/agent/ConversationSidebar.tsx`

- [ ] **Step 1: API client for settings**

```typescript
export function getContextSettings(token, novelId) { ... }
export function updateContextSettings(token, novelId, payload) { ... }
```

- [ ] **Step 2: Drawer with Switch per source + InputNumber for budget fields**

Labels in Chinese:
- 当前文档 / 选中文本 / 关键记忆 / 结构化素材 / 相邻章节 / RAG 检索 / 对话历史

- [ ] **Step 3: "上下文设置" button in sidebar footer opens drawer**

- [ ] **Step 4: Test: settings save calls PATCH**

---

### Task 11: Agent panel layout

**Files:**
- Modify: `frontend/src/features/agent/AgentPanel.tsx`
- Modify: `frontend/src/features/workspace/WorkspacePage.tsx` (grid if needed)

- [ ] **Step 1: Two-column layout inside Agent card**

```tsx
<Flex style={{ flex: 1, minHeight: 0 }}>
  <ConversationSidebar ... />
  <Flex vertical style={{ flex: 1, minWidth: 0 }}>
    <ContextStatusBar detail={contextDetail} />
    <Bubble.List ... />
    <Sender ... />
  </Flex>
</Flex>
```

- [ ] **Step 2: Conversation rename (inline or modal)**

PATCH `/conversations/{id}`.

- [ ] **Step 3: Delete conversation with confirm**

- [ ] **Step 4: Run frontend tests + manual Docker verify**

```bash
docker compose build web api && docker compose up -d
```

---

## Phase P5: Memory Tools + Memory Page

### Task 12: Wire agent memory tools

**Files:**
- Modify: `backend/app/agent/tools.py`
- Modify: `backend/app/agent/graph.py`
- Create: `backend/app/services/memory_search.py`
- Create: `backend/tests/test_memory_tools.py`

- [ ] **Step 1: Implement `search_memory` service**

Query `memory_items` by novel_id, order by importance. Return top 8.

- [ ] **Step 2: Implement `search_rag` tool using `search_rag_chunks`**

- [ ] **Step 3: Handle `draft_key_memory` intent**

In `agent.py` / graph: create `MemoryReviewItem` with `memory_type=key_memory`, return message "已提交关键记忆，请在记忆页审核。"

- [ ] **Step 4: Test end-to-end**

```python
def test_remember_this_creates_review_item(client, auth_headers, novel):
    response = client.post(
        f"/novels/{novel['id']}/agent/messages",
        headers=auth_headers,
        json={"message": "记住：主角不能背叛病人"},
    )
    reviews = client.get(f"/novels/{novel['id']}/memory-review-items", headers=auth_headers).json()
    assert any("背叛" in item["body"] for item in reviews)
```

---

### Task 13: Memory page — approved items

**Files:**
- Modify: `frontend/src/features/workspace/WorkspacePage.tsx`

- [ ] **Step 1: Load `listMemoryItems` alongside review items**

- [ ] **Step 2: Tabs: "待审核" | "已确认"**

- [ ] **Step 3: Style `context_snapshot` type with distinct Tag color**

- [ ] **Step 4: Test memory section renders approved items**

---

## Final Verification

- [ ] **Backend full suite**

```bash
docker compose run --rm api pytest tests/test_conversations.py tests/test_context_settings.py tests/test_context_assembly.py tests/test_context_compression.py tests/test_memory_tools.py -v
```

- [ ] **Frontend tests**

```bash
cd frontend && npm test -- --run
```

- [ ] **Manual checklist**

1. Create two conversations; switch between them; history is isolated.
2. Send message referencing prior turn; Agent responds with continuity.
3. Approve a key memory; next message's context bar shows memory source.
4. Fill long history; context bar shows compression warning / lower usage after auto-compress.
5. Open context settings; disable RAG; next run context_detail excludes rag_result.
6. Say "记住这个…"; item appears in memory review queue.

---

## Plan Self-Review

| Spec section | Task coverage |
|--------------|---------------|
| conversations + messages tables | Task 1–3 |
| novel_context_settings | Task 5, 10 |
| context_assembly all sources | Task 6 |
| compression 85/95% | Task 8 |
| context_snapshots | Task 8 |
| context_packs persistence | Task 8 |
| API conversations + settings | Task 2, 5 |
| Agent conversation_id + persistence | Task 3, 4 |
| context_detail in responses | Task 7 |
| Frontend sidebar + status + settings | Task 9–11 |
| Memory tools + memory page | Task 12–13 |
| LangGraph checkpoints | Deferred (not in this plan) |

No placeholders remain. Types consistent across backend schemas and frontend `conversations.ts` / `agent.ts`.
