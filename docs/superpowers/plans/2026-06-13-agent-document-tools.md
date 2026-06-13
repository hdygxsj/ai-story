# Agent Document Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add safely scoped Agent document mutation proposals, version restoration, and workspace-node restoration.

**Architecture:** Bind runtime tools to the authenticated user and current novel, centralize document mutations in a service, and reuse pending confirmations for destructive writes. Use document timestamps for optimistic concurrency and preserve every replaced body as a version.

**Tech Stack:** FastAPI, SQLAlchemy asyncio, LangChain tools, pytest, React, TypeScript, Vitest

---

### Task 1: Scoped document proposal service

**Files:**
- Create: `backend/app/services/document_actions.py`
- Test: `backend/tests/test_document_actions.py`

- [ ] Write failing tests proving out-of-scope documents are hidden, proposals capture `updated_at`, selection replacement changes only the unique selected text, and stale proposals are rejected.
- [ ] Run `cd backend && .venv/bin/pytest tests/test_document_actions.py -v` and verify failures are caused by the missing service.
- [ ] Implement ownership-aware lookup, proposal creation, text conversion, version snapshots, concurrency validation, mutation, and reindexing.
- [ ] Re-run the focused tests and verify they pass.

### Task 2: Agent runtime tools and scope injection

**Files:**
- Modify: `backend/app/agent/tools.py`
- Modify: `backend/app/agent/tool_runtime.py`
- Modify: `backend/app/agent/runtime.py`
- Modify: `backend/app/api/routes/agent.py`
- Modify: `backend/app/agent/chat_stream.py`
- Test: `backend/tests/test_langchain_tools.py`

- [ ] Write failing tests for the five registered tools and cross-novel rejection.
- [ ] Run the focused tests and confirm the new tools are missing.
- [ ] Add argument schemas and runtime implementations bound to `owner_id` and `novel_id`.
- [ ] Pass scope from authenticated Agent endpoints into graph invocation and streaming.
- [ ] Re-run the focused tests and verify they pass.

### Task 3: Confirmation execution and version APIs

**Files:**
- Modify: `backend/app/schemas/confirmation.py`
- Modify: `backend/app/api/routes/confirmations.py`
- Modify: `backend/app/api/routes/novels.py`
- Test: `backend/tests/test_agent_confirmations.py`

- [ ] Write failing API tests for update approval, selection approval, stale rejection, version listing, restore approval, and ownership isolation.
- [ ] Run the focused tests and confirm expected failures.
- [ ] Dispatch confirmation actions through the document action service and expose document version listing.
- [ ] Return mutation metadata needed for frontend refresh.
- [ ] Re-run the focused tests and verify they pass.

### Task 4: Workspace-node restoration

**Files:**
- Modify: `backend/app/services/workspace_actions.py`
- Modify: `backend/app/agent/tool_runtime.py`
- Test: `backend/tests/test_langchain_tools.py`

- [ ] Write failing tests for restoring a trashed node and rejecting active/out-of-scope nodes.
- [ ] Run the focused tests and confirm failures.
- [ ] Implement scoped restoration and return updated workspace nodes/diff.
- [ ] Re-run the focused tests and verify they pass.

### Task 5: Frontend refresh after confirmation

**Files:**
- Modify: `frontend/src/api/confirmations.ts`
- Modify: the workspace confirmation consumer identified during implementation
- Test: `frontend/src/test/workspace.test.tsx`

- [ ] Write a failing test proving an approved document confirmation reloads the active document.
- [ ] Run `cd frontend && npm test -- workspace.test.tsx` and confirm the expected failure.
- [ ] Add response typing and invoke the existing document/workspace refresh callback after approval.
- [ ] Re-run the focused frontend test and verify it passes.

### Task 6: Verification

**Files:**
- Modify only files required by failures found during verification.

- [ ] Run `cd backend && .venv/bin/pytest -v`.
- [ ] Run `cd backend && .venv/bin/ruff check app tests`.
- [ ] Run `cd frontend && npm test`.
- [ ] Run `cd frontend && npm run lint`.
- [ ] Run `cd frontend && npm run build`.
- [ ] Inspect `git diff --check` and the final scoped diff.
