# Context Source Accuracy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep Agent context sources accurate, compact, and synchronized with the material and timeline pages.

**Architecture:** Filter duplicate and inactive RAG sources in the backend assembly query, retain detailed item accounting in the API, and aggregate only the visual chips in the frontend. Add one Agent completion callback that reloads persisted creative collections after tool-driven writes.

**Tech Stack:** FastAPI, SQLAlchemy, React, TypeScript, Ant Design, pytest, Vitest

---

### Task 1: Backend Context Filtering

**Files:**
- Modify: `backend/app/services/rag.py`
- Modify: `backend/app/services/context_assembly.py`
- Test: `backend/tests/test_context_assembly.py`

- [ ] Add failing tests proving structured source types and trashed documents are excluded from assembled RAG context.
- [ ] Run the focused backend tests and confirm the expected failures.
- [ ] Add source-type exclusion to `search_rag_chunks` and filter inactive document chunks through active workspace nodes.
- [ ] Exclude trashed nodes from neighboring chapter loading.
- [ ] Run the focused backend tests and confirm they pass.

### Task 2: Group Context Status Chips

**Files:**
- Modify: `frontend/src/features/agent/ContextStatusBar.tsx`
- Create: `frontend/src/test/context-status-bar.test.tsx`

- [ ] Add a failing component test asserting repeated sources render once with an item count.
- [ ] Run the focused frontend test and confirm the expected failure.
- [ ] Aggregate items by source while preserving compressed state and total tokens.
- [ ] Run the focused frontend test and confirm it passes.

### Task 3: Refresh Creative Collections After Agent Writes

**Files:**
- Modify: `frontend/src/features/agent/AgentPanel.tsx`
- Modify: `frontend/src/features/workspace/WorkspacePage.tsx`
- Test: `frontend/src/test/workspace.test.tsx`

- [ ] Add a failing workspace test proving an Agent completion reloads materials and timeline data.
- [ ] Run the focused frontend test and confirm the expected failure.
- [ ] Add a completion callback to `AgentPanel` and reload all creative collections in `WorkspacePage`.
- [ ] Run the focused frontend test and confirm it passes.

### Task 4: Regression Verification

**Files:**
- Verify only

- [ ] Run backend context, RAG, material, and workspace tests.
- [ ] Run frontend tests.
- [ ] Run the frontend production build.
- [ ] Review the final diff for unrelated changes.
