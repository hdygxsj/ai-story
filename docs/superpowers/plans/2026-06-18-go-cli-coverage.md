# Go CLI Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Go `ai-story` CLI that covers all backend HTTP APIs and all Agent runtime tools, with `--help` support and repository synchronization rules.

**Architecture:** The CLI is a standalone Go HTTP client under `cli/`. Backend Agent runtime tools become callable through authenticated HTTP endpoints that reuse `build_runtime_tools`, so the CLI never connects to the database directly.

**Tech Stack:** Go 1.23 standard library, FastAPI, Pydantic, pytest, existing backend `httpx` dependency.

---

### Task 1: Backend Agent Tool API

**Files:**
- Create: `backend/app/schemas/agent_tools.py`
- Create: `backend/app/api/routes/agent_tools.py`
- Modify: `backend/app/api/routes/__init__.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_agent_tool_api.py`

- [ ] **Step 1: Write failing tests**

Create backend tests that prove `/agent-tools` lists every `get_agent_tools()` entry, `/agent-tools/calculate` exposes the argument schema, tool execution runs `calculate`, and tool execution rejects novels not owned by the authenticated user.

- [ ] **Step 2: Run tests to verify failure**

Run: `cd backend && env PYTHONPATH=. pytest -v tests/test_agent_tool_api.py`

Expected: FAIL because `/agent-tools` routes do not exist.

- [ ] **Step 3: Implement schemas and route**

Add `AgentToolInfo`, `AgentToolRunRequest`, and `AgentToolRunResponse`. Implement authenticated `GET /agent-tools`, `GET /agent-tools/{tool_name}`, and `POST /novels/{novel_id}/agent/tools/{tool_name}`. Use `get_owned_novel()` before execution and `build_runtime_tools()` for actual runtime behavior.

- [ ] **Step 4: Run backend tool API tests**

Run: `cd backend && env PYTHONPATH=. pytest -v tests/test_agent_tool_api.py`

Expected: PASS.

### Task 2: Go CLI Skeleton, Help, Config, And HTTP Client

**Files:**
- Create: `cli/go.mod`
- Create: `cli/cmd/ai-story/main.go`
- Create: `cli/internal/command/command.go`
- Create: `cli/internal/config/config.go`
- Create: `cli/internal/client/client.go`
- Create: `cli/internal/output/output.go`
- Test: `cli/internal/command/command_test.go`
- Test: `cli/internal/config/config_test.go`
- Test: `cli/internal/client/client_test.go`

- [ ] **Step 1: Write failing Go tests**

Create tests for top-level help containing `auth`, `api`, `tools`, `agent`, and `config`; base URL priority of flag over `AI_STORY_API_BASE` over saved config over default; and Authorization header insertion by the HTTP client.

- [ ] **Step 2: Run tests to verify failure**

Run: `cd cli && go test ./...`

Expected: FAIL because the Go module and packages do not exist.

- [ ] **Step 3: Implement minimal Go skeleton**

Implement a small command tree, generated help, config persistence, HTTP JSON client, and output helpers using the Go standard library.

- [ ] **Step 4: Run Go tests**

Run: `cd cli && go test ./...`

Expected: PASS.

### Task 3: CLI API, Auth, And Tool Commands

**Files:**
- Create: `cli/internal/coverage/routes.go`
- Create: `cli/internal/coverage/tools.go`
- Modify: `cli/internal/command/command.go`
- Test: `cli/internal/coverage/coverage_test.go`
- Test: `cli/internal/command/api_test.go`
- Test: `cli/internal/command/tools_test.go`

- [ ] **Step 1: Write failing tests**

Create tests that verify route coverage metadata contains every current backend route pattern; tool coverage metadata contains every current Agent tool name; `api request` sends the requested method/path; `tools run` sends `POST /novels/{novel_id}/agent/tools/{tool}`; `--arg`, `--json-arg`, and `--help` work.

- [ ] **Step 2: Run tests to verify failure**

Run: `cd cli && go test ./...`

Expected: FAIL because command behavior is missing.

- [ ] **Step 3: Implement commands**

Implement `auth register/login/me/logout`, `api request`, `api routes`, grouped API help nodes, `tools list/schema/run`, and `agent ask/stream` using the generic HTTP client.

- [ ] **Step 4: Run Go tests**

Run: `cd cli && go test ./...`

Expected: PASS.

### Task 4: AGENTS Rule, Build Wiring, And Verification

**Files:**
- Create: `AGENTS.md`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Update docs and wiring**

Add the required CLI synchronization rule to `AGENTS.md`. Add `cli-test` and `cli-build` targets to `Makefile`. Document basic CLI usage in `README.md`.

- [ ] **Step 2: Run final verification**

Run:

```bash
cd backend && env PYTHONPATH=. pytest -v tests/test_agent_tool_api.py
cd cli && go test ./...
cd cli && go build ./cmd/ai-story
```

Expected: all commands exit 0.
