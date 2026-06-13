# Automatic Memory and User Deletion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save explicit and Agent-inferred memories immediately without approval, while allowing owners to view and permanently delete each memory and its RAG index.

**Architecture:** Centralize formal memory creation and deletion in `app.services.memory`, then make the REST API, deterministic remember intent, and LangChain runtime tool call that service. Keep legacy review tables and routes for compatibility, but remove them from active Agent and frontend workflows. The frontend renders one formal-memory list with a confirmed delete action.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, pytest, LangChain tools, React 19, TypeScript, Ant Design, Vitest, Testing Library.

---

## File Map

- Modify `backend/app/services/memory.py`: shared create-and-index and delete-with-index-cleanup operations.
- Modify `backend/app/api/routes/memory.py`: direct formal-memory creation and owner-scoped deletion endpoints; retain legacy review endpoints.
- Modify `backend/app/agent/tools.py`: expose `save_key_memory` instead of `propose_key_memory` in the static tool registry.
- Modify `backend/app/agent/tool_runtime.py`: persist inferred memories directly through the shared service.
- Modify `backend/app/api/routes/agent.py`: persist explicit remember intent directly through the shared service.
- Modify `backend/app/agent/graph.py`: tell the model to save durable inferred facts without approval.
- Modify `backend/app/agent/chat_stream.py`: reinforce automatic durable-memory behavior in the runtime prompt.
- Modify `backend/tests/test_memory.py`: direct creation, deletion, ownership, repeat deletion, and legacy compatibility API tests.
- Modify `backend/tests/test_rag_memory.py`: verify direct memories are indexed and deleted chunks disappear from search.
- Modify `backend/tests/test_agent_memory_intent.py`: verify explicit remember intent creates formal memory only.
- Modify `backend/tests/test_langchain_tools.py`: verify the renamed runtime tool persists and indexes formal memory.
- Modify `frontend/src/api/memory.ts`: formal create/delete client functions and removal of active review helpers.
- Modify `frontend/src/features/workspace/WorkspacePage.tsx`: one memory list with confirmation-based deletion.
- Modify `frontend/src/test/data-flow.test.tsx`: render and delete behavior tests.
- Modify `README.md`: describe automatic memory and user deletion instead of memory approval.

### Task 1: Shared Formal Memory Service

**Files:**
- Modify: `backend/app/services/memory.py`
- Test: `backend/tests/test_memory.py`

- [ ] **Step 1: Write failing service tests for creation and deletion**

Add async tests using the existing `session` fixture. Create a `User` and `Novel`, call the new service, and assert both `MemoryItem` and `RagChunk` exist. Then delete it and assert both are gone.

```python
async def test_create_memory_item_persists_and_indexes(session) -> None:
    user = User(email="service-memory@example.com", username="service-memory", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Service Memory")
    session.add(novel)
    await session.flush()

    memory = await create_memory_item(
        session,
        novel_id=novel.id,
        memory_type="key_memory",
        title="Core vow",
        body="Never betray a patient.",
        importance=100,
        metadata={"source": "user_explicit"},
    )
    await session.commit()

    chunk = await session.scalar(
        select(RagChunk).where(RagChunk.source_type == "memory", RagChunk.source_id == str(memory.id))
    )
    assert memory.id is not None
    assert chunk is not None
    assert chunk.text == "Core vow\nNever betray a patient."


async def test_delete_memory_item_removes_memory_and_index(session) -> None:
    user = User(email="delete-memory@example.com", username="delete-memory", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Delete Memory")
    session.add(novel)
    await session.flush()
    memory = await create_memory_item(
        session,
        novel_id=novel.id,
        memory_type="key_memory",
        title="Temporary clue",
        body="The map is under the lighthouse.",
        importance=80,
    )
    await session.commit()

    deleted = await delete_memory_item(
        session,
        owner_id=user.id,
        item_id=memory.id,
    )
    await session.commit()

    assert deleted is True
    assert await session.get(MemoryItem, memory.id) is None
    assert await session.scalar(
        select(RagChunk).where(RagChunk.source_type == "memory", RagChunk.source_id == str(memory.id))
    ) is None
```

- [ ] **Step 2: Run the service tests and verify RED**

Run:

```bash
cd backend && uv run pytest tests/test_memory.py -k "create_memory_item_persists or delete_memory_item_removes" -v
```

Expected: FAIL because `create_memory_item` and `delete_memory_item` do not exist.

- [ ] **Step 3: Implement the shared service operations**

Replace the approval-only service with these operations while retaining `approve_review_item` for legacy routes:

```python
from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import MemoryItem, MemoryReviewItem, Novel, RagChunk
from app.services.rag import index_text


async def create_memory_item(
    session: AsyncSession,
    *,
    novel_id: UUID,
    memory_type: str,
    title: str,
    body: str,
    importance: int = 50,
    metadata: dict[str, Any] | None = None,
) -> MemoryItem:
    memory = MemoryItem(
        novel_id=novel_id,
        memory_type=memory_type,
        title=title,
        body=body,
        importance=importance,
        extra_metadata=metadata or {},
    )
    session.add(memory)
    await session.flush()
    await index_text(
        session,
        novel_id=novel_id,
        source_type="memory",
        source_id=str(memory.id),
        text=f"{title}\n{body}",
        metadata={"memory_type": memory_type, "importance": importance, **(metadata or {})},
    )
    return memory


async def delete_memory_item(session: AsyncSession, *, owner_id: UUID, item_id: UUID) -> bool:
    memory = await session.scalar(
        select(MemoryItem)
        .join(Novel, Novel.id == MemoryItem.novel_id)
        .where(MemoryItem.id == item_id, Novel.owner_id == owner_id)
    )
    if memory is None:
        return False
    await session.execute(
        delete(RagChunk).where(
            RagChunk.novel_id == memory.novel_id,
            RagChunk.source_type == "memory",
            RagChunk.source_id == str(memory.id),
        )
    )
    await session.delete(memory)
    return True
```

- [ ] **Step 4: Run the service tests and verify GREEN**

Run the command from Step 2.

Expected: PASS; the formal memory and RAG chunk are created and deleted together.

- [ ] **Step 5: Commit the service change**

```bash
git add backend/app/services/memory.py backend/tests/test_memory.py
git commit -m "Add formal memory lifecycle service"
```

### Task 2: Direct Memory REST API and Owner-Scoped Deletion

**Files:**
- Modify: `backend/app/api/routes/memory.py`
- Modify: `backend/tests/test_memory.py`
- Modify: `backend/tests/test_rag_memory.py`

- [ ] **Step 1: Write failing API tests**

Add tests proving `POST /novels/{id}/memory-items` returns 201 and immediately appears in the formal list, `DELETE /memory-items/{id}` returns 204, a second delete returns 404, and another user receives 404.

```python
def test_memory_is_created_without_review_and_can_be_deleted() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Memory Book"}).json()

    created = client.post(
        f"/novels/{novel['id']}/memory-items",
        headers=headers,
        json={
            "memory_type": "key_memory",
            "title": "Protagonist constraint",
            "body": "The protagonist must never willingly betray a patient.",
            "importance": 100,
            "metadata": {"source": "user_explicit"},
        },
    )

    assert created.status_code == 201
    assert client.get(f"/novels/{novel['id']}/memory-items", headers=headers).json()[0]["id"] == created.json()["id"]
    assert client.get(f"/novels/{novel['id']}/memory-review-items", headers=headers).json() == []
    assert client.delete(f"/memory-items/{created.json()['id']}", headers=headers).status_code == 204
    assert client.delete(f"/memory-items/{created.json()['id']}", headers=headers).status_code == 404
```

Update the RAG test to create directly, search successfully, delete, then assert the same query returns no memory result.

- [ ] **Step 2: Run API tests and verify RED**

```bash
cd backend && uv run pytest tests/test_memory.py tests/test_rag_memory.py -k "memory" -v
```

Expected: FAIL with 405/404 for the new POST and DELETE paths.

- [ ] **Step 3: Add direct create and delete routes**

Import `Response`, `create_memory_item`, and `delete_memory_item`. Add:

```python
@router.post(
    "/novels/{novel_id}/memory-items",
    response_model=MemoryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_formal_memory_item(
    novel_id: UUID,
    payload: MemoryReviewCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> MemoryItem:
    await get_owned_novel(session, current_user, novel_id)
    memory = await create_memory_item(
        session,
        novel_id=novel_id,
        memory_type=payload.memory_type,
        title=payload.title,
        body=payload.body,
        importance=payload.importance,
        metadata=payload.metadata,
    )
    await session.commit()
    await session.refresh(memory)
    return memory


@router.delete("/memory-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_formal_memory_item(
    item_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Response:
    deleted = await delete_memory_item(session, owner_id=current_user.id, item_id=item_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory item not found")
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
```

Keep the old review routes unchanged for compatibility.

- [ ] **Step 4: Run API tests and verify GREEN**

Run the command from Step 2.

Expected: PASS, including RAG search after create and absence after delete.

- [ ] **Step 5: Commit the API change**

```bash
git add backend/app/api/routes/memory.py backend/tests/test_memory.py backend/tests/test_rag_memory.py
git commit -m "Add automatic memory API and deletion"
```

### Task 3: Explicit Remember Intent Saves Immediately

**Files:**
- Modify: `backend/app/api/routes/agent.py`
- Modify: `backend/tests/test_agent_memory_intent.py`

- [ ] **Step 1: Rewrite the intent test for formal memory behavior**

```python
def test_explicit_memory_intent_creates_formal_memory_without_review() -> None:
    client = TestClient(app)
    headers = auth_headers(client)
    novel = client.post("/novels", headers=headers, json={"title": "Memory Intent Novel"}).json()

    with client.stream(
        "POST",
        f"/novels/{novel['id']}/agent/messages/stream",
        headers=headers,
        json={"message": "记住：主角不能背叛病人"},
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert "已保存到记忆" in body
    memories = client.get(f"/novels/{novel['id']}/memory-items", headers=headers).json()
    reviews = client.get(f"/novels/{novel['id']}/memory-review-items", headers=headers).json()
    assert any("背叛" in item["body"] for item in memories)
    assert reviews == []
```

- [ ] **Step 2: Run the intent test and verify RED**

```bash
cd backend && uv run pytest tests/test_agent_memory_intent.py -v
```

Expected: FAIL because the route still creates `MemoryReviewItem` and asks for review.

- [ ] **Step 3: Route explicit intent through `create_memory_item`**

Replace the `MemoryReviewItem` construction with:

```python
memory = await create_memory_item(
    session,
    novel_id=novel_id,
    memory_type="key_memory",
    title=payload.message[:60] or "关键记忆",
    body=payload.message,
    importance=80,
    metadata={"source": "user_explicit"},
)
await session.commit()
response = "已保存到记忆。"
```

Change the done-event status to `["已保存关键记忆。"]` and remove the now-unused `MemoryReviewItem` import.

- [ ] **Step 4: Run the intent test and verify GREEN**

Run the command from Step 2.

Expected: PASS; no review row is created.

- [ ] **Step 5: Commit the explicit intent change**

```bash
git add backend/app/api/routes/agent.py backend/tests/test_agent_memory_intent.py
git commit -m "Save explicit memories without approval"
```

### Task 4: Agent-Inferred Memory Tool Saves Immediately

**Files:**
- Modify: `backend/app/agent/tools.py`
- Modify: `backend/app/agent/tool_runtime.py`
- Modify: `backend/tests/test_langchain_tools.py`

- [ ] **Step 1: Write failing registry and runtime tests**

Change the registry expectation from `propose_key_memory` to `save_key_memory`, and add:

```python
async def test_save_key_memory_tool_persists_formal_memory(session) -> None:
    user = User(email="tool-memory@example.com", username="tool-memory", password_hash="hash")
    session.add(user)
    await session.flush()
    novel = Novel(owner_id=user.id, title="Tool Memory")
    session.add(novel)
    await session.commit()

    tools = {
        tool.name: tool
        for tool in build_runtime_tools(
            session, model_profile=None, owner_id=user.id, novel_id=novel.id
        )
    }
    result = await tools["save_key_memory"].ainvoke(
        {
            "novel_id": str(novel.id),
            "title": "Hidden lineage",
            "body": "Mira is the last heir.",
            "importance": 90,
        }
    )

    memories = list(await session.scalars(select(MemoryItem).where(MemoryItem.novel_id == novel.id)))
    reviews = list(await session.scalars(select(MemoryReviewItem).where(MemoryReviewItem.novel_id == novel.id)))
    assert result["action_type"] == "memory_saved"
    assert memories[0].title == "Hidden lineage"
    assert memories[0].extra_metadata["source"] == "agent_inferred"
    assert reviews == []
```

- [ ] **Step 2: Run the tool tests and verify RED**

```bash
cd backend && uv run pytest tests/test_langchain_tools.py -k "tool_registry or save_key_memory" -v
```

Expected: FAIL because the registry and runtime still expose `propose_key_memory`.

- [ ] **Step 3: Rename the tool and use the service**

Rename `ProposeKeyMemoryArgs` to `SaveKeyMemoryArgs`, the static tool to `save_key_memory`, and update `get_agent_tools()`. In `tool_runtime.py`, replace the review-item implementation with:

```python
@tool("save_key_memory", args_schema=SaveKeyMemoryArgs)
async def save_key_memory_runtime(
    novel_id: str, title: str, body: str, importance: int = 80
) -> dict[str, Any]:
    """Save durable novel memory without approval."""
    memory = await create_memory_item(
        session,
        novel_id=current_novel_id(novel_id),
        memory_type="key_memory",
        title=title,
        body=body,
        importance=importance,
        metadata={"source": "agent_inferred"},
    )
    await session.commit()
    await session.refresh(memory)
    return {
        "status": "ok",
        "action_type": "memory_saved",
        "message": f"已保存关键记忆「{title}」。",
        "memory_item_id": str(memory.id),
    }
```

Remove runtime imports and registry entries that are only needed for proposing review items. Remove `list_memory_review_items` from the active Agent tool registry because the Agent no longer has an approval workflow; leave the legacy REST review routes and database model intact for compatibility.

- [ ] **Step 4: Run the tool tests and verify GREEN**

Run the command from Step 2.

Expected: PASS; formal memory exists, review list is empty, and indexing is covered through the shared service test.

- [ ] **Step 5: Commit the Agent tool change**

```bash
git add backend/app/agent/tools.py backend/app/agent/tool_runtime.py backend/tests/test_langchain_tools.py
git commit -m "Save inferred Agent memories directly"
```

### Task 5: Prompt the Agent to Capture Durable Inferences

**Files:**
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/app/agent/chat_stream.py`
- Test: `backend/tests/test_langchain_tools.py`

- [ ] **Step 1: Add a failing prompt assertion**

Add a focused test for `_default_system_prompt` or `_build_agent_system_prompt` asserting the prompt mentions `save_key_memory`, durable future-relevant information, no approval, and avoiding transient or duplicate memory.

```python
def test_agent_prompt_allows_selective_automatic_memory() -> None:
    prompt = _default_system_prompt({"novel_id": uuid4()})
    assert "save_key_memory" in prompt
    assert "无需用户审批" in prompt
    assert "临时信息或重复内容" in prompt
```

- [ ] **Step 2: Run the prompt test and verify RED**

```bash
cd backend && uv run pytest tests/test_langchain_tools.py -k "automatic_memory" -v
```

Expected: FAIL because the prompt has no automatic-memory guidance.

- [ ] **Step 3: Add selective automatic-memory guidance**

Append the same guidance to both graph prompt builders:

```python
"当对话中出现会影响后续创作的持久事实、约束、偏好、角色状态或剧情信息时，调用 save_key_memory 直接保存，无需用户审批。不要保存临时信息或重复内容。"
```

Update `chat_stream.py` tool summary to name automatic memory saving explicitly so streamed execution receives the same contract.

- [ ] **Step 4: Run the prompt test and verify GREEN**

Run the command from Step 2.

Expected: PASS.

- [ ] **Step 5: Commit the prompt change**

```bash
git add backend/app/agent/graph.py backend/app/agent/chat_stream.py backend/tests/test_langchain_tools.py
git commit -m "Guide Agent automatic memory capture"
```

### Task 6: Frontend Formal Memory List and Delete Control

**Files:**
- Modify: `frontend/src/api/memory.ts`
- Modify: `frontend/src/features/workspace/WorkspacePage.tsx`
- Modify: `frontend/src/test/data-flow.test.tsx`

- [ ] **Step 1: Write failing UI tests**

Update the fetch stub so `GET /novels/novel-1/memory-items` returns a formal memory. Add a `DELETE /memory-items/memory-1` branch returning 204. Test that the memory page has no pending-review tab, displays the automatic-saving explanation and body, and deletes after confirming the Ant Design popconfirm.

```tsx
it("shows automatic memories and lets the user delete one", async () => {
  const user = userEvent.setup();
  render(<WorkspacePage activeSection="memory" token="token" novelId="novel-1" />);

  expect(await screen.findByText("Core vow")).toBeInTheDocument();
  expect(screen.getByText("Never forget the lighthouse.")).toBeInTheDocument();
  expect(screen.getByText(/自动保存/)).toBeInTheDocument();
  expect(screen.queryByRole("tab", { name: "待审核" })).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "删除" }));
  await user.click(await screen.findByRole("button", { name: "确认删除" }));

  await waitFor(() => expect(screen.queryByText("Core vow")).not.toBeInTheDocument());
  expect(fetch).toHaveBeenCalledWith(
    "http://localhost:8000/memory-items/memory-1",
    expect.objectContaining({ method: "DELETE" }),
  );
});
```

- [ ] **Step 2: Run the UI test and verify RED**

```bash
cd frontend && npm test -- --run src/test/data-flow.test.tsx
```

Expected: FAIL because review tabs remain and no delete control exists.

- [ ] **Step 3: Update the memory API client**

Keep `MemoryItem`, add direct creation for callers, and add deletion:

```typescript
export function createMemoryItem(
  token: string,
  novelId: string,
  payload: Omit<MemoryItem, "id"> & { metadata?: Record<string, unknown> },
) {
  return apiRequest<MemoryItem>(`/novels/${novelId}/memory-items`, {
    method: "POST",
    token,
    body: JSON.stringify(payload),
  });
}

export function deleteMemoryItem(token: string, itemId: string) {
  return apiRequest<void>(`/memory-items/${itemId}`, { method: "DELETE", token });
}
```

Legacy review exports may remain temporarily if other code imports them, but `WorkspacePage` must stop using them.

- [ ] **Step 4: Replace review state and tabs with one list**

Import `Popconfirm`, remove `memoryReviews`, `memoryReviewCount`, review loading, and `resolveMemoryReview`. Add:

```tsx
async function removeMemory(itemId: string) {
  await deleteMemoryItem(token, itemId);
  setMemoryItems((items) => items.filter((item) => item.id !== itemId));
}
```

Render one `List` whose items show title, body, type, and importance. Add:

```tsx
<Popconfirm
  title="删除这条记忆？"
  description="删除后，Agent 将无法再从长期记忆中检索它。"
  okText="确认删除"
  cancelText="取消"
  onConfirm={() => removeMemory(item.id)}
>
  <Button danger size="small">删除</Button>
</Popconfirm>
```

Use the page description: `Agent 检测到的长期信息和你明确要求记录的内容会自动保存，你可以随时删除。`

- [ ] **Step 5: Run the UI test and verify GREEN**

Run the command from Step 2.

Expected: PASS; the item disappears only after confirmed successful deletion.

- [ ] **Step 6: Add and test deletion failure behavior**

Add a test whose DELETE branch returns status 500 and assert the memory remains visible. In `removeMemory`, wrap the call with `try/catch`, call `message.error("删除记忆失败")`, and leave state unchanged on failure.

Run:

```bash
cd frontend && npm test -- --run src/test/data-flow.test.tsx
```

Expected: PASS for both success and failure cases.

- [ ] **Step 7: Commit the frontend change**

```bash
git add frontend/src/api/memory.ts frontend/src/features/workspace/WorkspacePage.tsx frontend/src/test/data-flow.test.tsx
git commit -m "Add user-controlled memory deletion UI"
```

### Task 7: Documentation and Full Regression Verification

**Files:**
- Modify: `README.md`
- Verify: all memory, Agent, confirmation, and frontend tests

- [ ] **Step 1: Update the README behavior summary**

Replace `Key memory review and approval.` with:

```markdown
- Automatic long-term memory capture with user-controlled viewing and deletion.
```

Keep document and destructive-action approval documentation unchanged.

- [ ] **Step 2: Run backend formatting and focused tests**

```bash
cd backend && uv run ruff check app/services/memory.py app/api/routes/memory.py app/api/routes/agent.py app/agent/tools.py app/agent/tool_runtime.py app/agent/graph.py app/agent/chat_stream.py tests/test_memory.py tests/test_rag_memory.py tests/test_agent_memory_intent.py tests/test_langchain_tools.py
cd backend && uv run pytest tests/test_memory.py tests/test_rag_memory.py tests/test_agent_memory_intent.py tests/test_langchain_tools.py tests/test_agent_confirmations.py tests/test_document_actions.py -v
```

Expected: lint clean and all focused backend tests PASS. Confirmation tests prove non-memory destructive operations still require approval.

- [ ] **Step 3: Run the full backend suite**

```bash
cd backend && uv run pytest -v
```

Expected: all backend tests PASS.

- [ ] **Step 4: Run frontend tests, lint, and build**

```bash
cd frontend && npm test
cd frontend && npm run lint
cd frontend && npm run build
```

Expected: all tests PASS, lint clean, and production build succeeds.

- [ ] **Step 5: Manually verify the local workflow**

With the app running:

1. Send `记住：主角不能背叛病人`.
2. Confirm the Agent replies that the memory was saved without an approval card.
3. Open the memory page and confirm the item appears directly.
4. Trigger an Agent-inferred durable fact and confirm it also appears.
5. Delete one memory, refresh the page, and confirm it stays deleted.
6. Search or chat about the deleted fact and confirm it is no longer retrieved from memory/RAG.
7. Trigger a document replacement and confirm its approval card still appears.

- [ ] **Step 6: Commit documentation and any verification fixes**

```bash
git add README.md
git commit -m "Document automatic memory behavior"
```

Do not include unrelated pre-existing workspace changes in this commit.
