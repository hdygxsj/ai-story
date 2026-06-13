# Automatic Memory and User Deletion Design

**Date:** 2026-06-13

## Goal

All long-term memories are saved without user approval. This includes memories explicitly requested by the user and memories inferred by the Agent. Users retain control through the memory page, where every stored memory can be viewed and deleted.

This change applies only to memory. Existing confirmations for document replacement, version restoration, and other destructive workspace actions remain unchanged.

## Behavior

- A user request such as "记住这个" creates a `MemoryItem` immediately.
- When the Agent identifies a durable fact, constraint, preference, character state, timeline fact, summary, or other useful long-term context, its memory tool creates a `MemoryItem` immediately.
- Newly created memories are indexed for RAG in the same transaction flow as the database write.
- The Agent response reports that the memory was saved; it does not ask the user to review or approve it.
- The memory page shows the stored memories directly and no longer presents a pending-review tab or review count.
- Each memory has a delete action. The UI asks for confirmation before issuing the deletion request.
- Deleting a memory removes both the `MemoryItem` and every RAG chunk whose source is that memory.
- Ownership is checked through the memory's novel before deletion. A user cannot delete another user's memory.

## Architecture

### Memory Service

Add a shared service operation that accepts the novel scope and memory fields, creates a `MemoryItem`, flushes it to obtain its ID, indexes its text as `source_type=memory`, and leaves transaction commit control to the caller. All API and Agent paths use this operation so direct and inferred memories behave consistently.

Add a deletion operation that resolves a memory within the current user's novel scope, deletes matching `RagChunk` rows, then deletes the `MemoryItem`. Missing or out-of-scope memories return 404.

### API

The existing review endpoints are no longer part of the active frontend or Agent workflow. The memory collection creation endpoint is changed to create a formal memory directly and return `MemoryItemResponse`; its URL should become `POST /novels/{novel_id}/memory-items` to match its behavior.

Add `DELETE /memory-items/{item_id}`. A successful deletion returns HTTP 204.

The old review endpoints and table remain temporarily for database compatibility and historical rows, but no new application path writes to them. They can be removed in a later dedicated migration after deployments no longer depend on them.

### Agent Tools and Intent Path

Rename the tool-facing behavior from proposing a key memory to saving a key memory. The public tool name becomes `save_key_memory`, and its runtime implementation calls the shared memory service. Tool descriptions and system prompts explicitly permit the Agent to save durable inferred memories without approval.

The deterministic intent path used for explicit "remember this" requests also calls the same service. Its response becomes "已保存到记忆。" and its context status reports a saved memory rather than a review item.

Agent-inferred memory should still be selective: the model should save facts expected to matter in future work, not transient conversation or duplicate information. This is an Agent quality rule, not an approval gate.

### Frontend

The memory API module exposes list, create, and delete operations for formal memories. Review-specific API functions are no longer used by the workspace.

The memory page becomes one list titled "记忆". It explains that Agent-detected and user-requested memories are saved automatically and can be deleted at any time. Each row shows type, importance, title, and body, with a destructive delete action wrapped in a confirmation prompt. After deletion, the list reloads or removes the deleted item locally.

## Data Flow

1. The user explicitly requests memory, or the Agent calls `save_key_memory` after identifying durable context.
2. The shared service creates and flushes a `MemoryItem`.
3. The service replaces any matching RAG source chunks with the memory's current text and metadata.
4. The caller commits and returns the saved memory or a concise Agent result.
5. The memory appears in subsequent context assembly and on the memory page without approval.
6. When the user confirms deletion, the API verifies ownership, removes associated RAG chunks, removes the memory row, and commits.

## Error Handling

- If indexing fails, memory creation fails and the transaction rolls back rather than leaving an unindexed formal memory.
- Deleting an unknown or out-of-scope memory returns 404 without revealing whether it belongs to another user.
- Repeated deletion returns 404.
- The frontend keeps the item visible and surfaces the request error when deletion fails.

## Compatibility

Existing approved `MemoryItem` rows continue to work unchanged. Existing `MemoryReviewItem` rows remain in the database but are not shown in the revised memory UI and are not promoted automatically. This avoids silently approving historical drafts that users previously expected to review.

Existing RAG search and context assembly continue to query `MemoryItem`, so automatically saved memories require no retrieval changes. Context snapshots created by compression remain formal memories and are deletable through the same API.

## Testing

Backend tests cover:

- Explicit remember intent creates and indexes a formal memory without a review row.
- Agent `save_key_memory` creates and indexes a formal memory without approval.
- Direct memory creation returns a formal memory.
- An owner can delete a memory and its RAG chunks.
- Another user cannot delete the memory.
- Repeated deletion returns 404.
- Document and workspace confirmations still require approval.

Frontend tests cover:

- The memory page renders formal memories without a pending-review tab.
- The page explains automatic saving and user deletion.
- Confirmed deletion calls the delete API and removes the item.
- A failed deletion keeps the item visible and reports the error.

## Out of Scope

- Restoring deleted memories.
- Editing or merging memories.
- A per-user or per-novel automatic-memory toggle.
- Automatically promoting historical review items.
- Removing the review table and endpoints in the same database migration.
