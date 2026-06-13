# Workspace Layout Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add collapsible chapter navigation, a compact Agent header, an editor-scoped overview, and a persisted resizable Agent column.

**Architecture:** Keep layout ownership in `WorkspacePage`, where both side-column widths and visibility determine the CSS grid. Keep conversation behavior inside `AgentPanel` and `ConversationSidebar`, changing only their composition so controls render in the card header.

**Tech Stack:** React, TypeScript, Ant Design, Vitest, Testing Library, CSS Grid

---

### Task 1: Specify Layout State With Failing Tests

**Files:**
- Modify: `frontend/src/test/workspace.test.tsx`

- [ ] Add a test that collapses the chapter tree, verifies its column and separator disappear, restores it, and verifies local-storage persistence.
- [ ] Add a test that drags the Agent separator, verifies width clamping and local-storage persistence.
- [ ] Add assertions that the overview is in the editor column and conversation controls are in the Agent header.
- [ ] Run `npm test -- --run src/test/workspace.test.tsx` from `frontend` and confirm the new assertions fail for missing behavior.

### Task 2: Implement Workspace Grid Controls

**Files:**
- Modify: `frontend/src/features/workspace/WorkspacePage.tsx`

- [ ] Add persisted chapter visibility and Agent width state with clamp helpers.
- [ ] Add mouse-drag lifecycle handling for the Agent separator.
- [ ] Make grid columns conditional on chapter visibility and include the Agent separator.
- [ ] Place collapse/expand controls around the chapter and editor columns.
- [ ] Move the overview strip into the editor column.
- [ ] Run the focused workspace test and confirm the layout-state tests pass.

### Task 3: Compact The Agent Header

**Files:**
- Modify: `frontend/src/features/agent/AgentPanel.tsx`
- Modify: `frontend/src/features/agent/ConversationSidebar.tsx`
- Modify: `frontend/src/features/agent/agent-panel.css`

- [ ] Render conversation controls as a compact header control group rather than a body toolbar.
- [ ] Compose that control group with the Agent title in the Ant Design card header.
- [ ] Remove body spacing and border styles that belonged to the old toolbar row.
- [ ] Run the focused workspace and Agent-related frontend tests.

### Task 4: Verify The Complete Change

**Files:**
- Modify: `frontend/src/test/workspace.test.tsx` only if a test needs correction to match the approved behavior.

- [ ] Run `npm test -- --run src/test/workspace.test.tsx src/test/workspace-tree.test.tsx src/test/context-status-bar.test.tsx` from `frontend`.
- [ ] Run `npm run build` from `frontend`.
- [ ] Inspect `git diff` to confirm existing unrelated work remains intact and only the approved layout behavior was added.
