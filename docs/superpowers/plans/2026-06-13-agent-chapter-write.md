# Agent Chapter Write Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist Agent-written chapters to the workspace and immediately open the created document.

**Architecture:** Introduce an atomic chapter-writing workspace service and expose it through the runtime tool registry. Reuse the existing workspace tree response to notify the frontend, which selects the newly added document.

**Tech Stack:** FastAPI, SQLAlchemy, LangChain tools, React, TypeScript, pytest, Vitest

---

### Task 1: Atomic Chapter Write Tool

**Files:**
- Modify: `backend/app/agent/tools.py`
- Modify: `backend/app/agent/tool_runtime.py`
- Modify: `backend/app/services/workspace_actions.py`
- Test: `backend/tests/test_langchain_tools.py`

- [ ] Add failing tests for the registered tool and persisted chapter content.
- [ ] Run the focused tests and confirm failure.
- [ ] Implement atomic document, node, version, and index creation.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Agent Result Contract

**Files:**
- Modify: `backend/app/agent/graph.py`
- Modify: `backend/app/agent/chat_stream.py`
- Modify: `backend/app/api/routes/agent.py`
- Test: `backend/tests/test_langchain_tools.py`

- [ ] Add a failing graph test for workspace mutation propagation.
- [ ] Tighten the prompt so save claims require successful tool output.
- [ ] Propagate the created node and workspace nodes in sync and stream responses.
- [ ] Run Agent tests.

### Task 3: Open the Created Chapter

**Files:**
- Modify: `frontend/src/features/agent/AgentPanel.tsx`
- Modify: `frontend/src/features/workspace/WorkspacePage.tsx`
- Test: `frontend/src/test/workspace.test.tsx`

- [ ] Add a failing UI test for selecting the returned chapter document.
- [ ] Pass the created node through the existing workspace callback.
- [ ] Select and load the new document after Agent completion.
- [ ] Run frontend tests and build.
