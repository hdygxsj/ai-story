# AI Story Go CLI Design

## Goal

Build a Go-based `ai-story` CLI that exposes the product's complete backend surface for local authors and automation.

The CLI must cover:

- All current HTTP API routes.
- All current Agent runtime tools.
- Discoverable help through `--help` at every command level.
- A repository rule that backend API or Agent tool changes must update CLI coverage in the same change.

The CLI should behave as an HTTP client for the running backend. It must not connect directly to PostgreSQL or call backend Python services from the local process.

## Non-Goals

- The CLI will not replace the web or desktop UI.
- The CLI will not run migrations, install Docker, or manage the compose stack in this feature.
- The CLI will not bypass product safety rules such as authentication, ownership checks, confirmation records, or backend transactions.

## Repository Layout

Add a new Go module under `cli/`:

```text
cli/
  go.mod
  cmd/ai-story/main.go
  internal/command/
  internal/client/
  internal/config/
  internal/output/
```

The compiled binary is named `ai-story`.

The repository root will add `AGENTS.md` with a CLI synchronization rule:

```text
When adding, removing, or changing any backend HTTP API route or Agent runtime tool,
update the Go CLI command coverage, help text, and tests in the same change.
```

## Command Shape

Top-level commands:

```bash
ai-story auth ...
ai-story api ...
ai-story tools ...
ai-story agent ...
ai-story config ...
```

Every command and subcommand supports `--help`, including:

```bash
ai-story --help
ai-story api --help
ai-story api novels --help
ai-story tools --help
ai-story tools run --help
```

The CLI uses Go's standard library command parsing. Each command is registered with a name, summary, usage string, flags, child commands, and runner. Help output is generated from that registry so tests can verify coverage.

## Configuration And Auth

The CLI resolves the backend base URL in this order:

1. `--base-url`
2. `AI_STORY_API_BASE`
3. Saved config
4. `http://localhost:8000`

Authentication commands:

```bash
ai-story auth register --email EMAIL --username USERNAME --password PASSWORD
ai-story auth login --login EMAIL_OR_USERNAME --password PASSWORD
ai-story auth me
ai-story auth logout
```

The access token is stored in the CLI config directory with restrictive file permissions. Requests requiring authentication send `Authorization: Bearer <token>`.

## HTTP API Coverage

The `api` command exposes all backend HTTP routes. It includes grouped commands for the known routes and a raw request fallback.

Grouped command families:

```bash
ai-story api auth ...
ai-story api model-profiles ...
ai-story api novels ...
ai-story api workspace ...
ai-story api documents ...
ai-story api confirmations ...
ai-story api conversations ...
ai-story api context-settings ...
ai-story api memory ...
ai-story api materials ...
ai-story api rag ...
ai-story api search ...
ai-story api agent ...
```

Raw fallback:

```bash
ai-story api request METHOD PATH --body-json JSON
ai-story api request GET /novels
ai-story api request POST /novels --body-json '{"title":"New Novel"}'
```

The fallback ensures a route remains callable even before a polished convenience command is added, but tests must still assert first-class coverage for every known route.

HTTP route coverage includes:

- `/auth/register`, `/auth/login`, `/auth/me`
- `/model-profiles`, `/model-profiles/{profile_id}`, `/model-profiles/test-connectivity`
- `/novels`, `/novels/import`, `/novels/{novel_id}`, `/novels/{novel_id}/export`
- `/novels/{novel_id}/nodes`, node export, trash cleanup, reorder, update
- `/documents/{document_id}`, document versions, version restore
- `/novels/{novel_id}/confirmations`, confirmation history, approve, reject
- `/novels/{novel_id}/conversations`, conversation detail, update, delete, messages
- `/novels/{novel_id}/context-settings`
- memory review items and approved memory items
- creative assets, timeline events, character states, relationship edges, material changes
- `/novels/{novel_id}/rag/search`
- `/novels/{novel_id}/search`
- `/novels/{novel_id}/agent/messages`, `/novels/{novel_id}/agent/messages/stream`

## Agent Tool Coverage

The CLI must cover every tool returned by `get_agent_tools()`.

Some Agent tools do not have HTTP routes, so the backend will add a small authenticated tool execution API:

```text
GET  /agent-tools
GET  /agent-tools/{tool_name}
POST /novels/{novel_id}/agent/tools/{tool_name}
```

The list and detail endpoints return each tool's name, description, argument schema, and whether it needs novel or document scope.

The run endpoint executes the same runtime tool implementation used by the Agent graph, scoped to the authenticated user and target novel. It accepts:

```json
{
  "arguments": {},
  "document_id": null
}
```

The CLI exposes this as:

```bash
ai-story tools list
ai-story tools schema TOOL
ai-story tools run NOVEL_ID TOOL --arg key=value --json-arg key='{"nested":true}'
```

Examples:

```bash
ai-story tools run NOVEL_ID read_document --arg document_id=DOCUMENT_ID
ai-story tools run NOVEL_ID calculate --arg expression='(12 + 8) * 15%'
ai-story tools run NOVEL_ID global_replace_keyword --arg old_text=旧称 --arg new_text=新称 --arg dry_run=true
ai-story tools run NOVEL_ID delete_creative_assets --json-arg asset_ids='["id1","id2"]' --yes
```

Tool coverage includes:

- `read_document`
- `search_memory`
- `search_rag`
- `search_documents_by_keyword`
- `global_replace_keyword`
- `calculate`
- `get_server_time`
- `update_novel`
- `list_workspace_nodes`
- `create_workspace_node`
- `create_chapter_with_content`
- `write_document_content`
- `split_chapter_by_max_chars`
- `propose_document_update`
- `propose_selection_replace`
- `list_document_versions`
- `propose_version_restore`
- `restore_workspace_node`
- `update_workspace_node`
- `trash_workspace_node`
- `organize_workspace_tree`
- `cleanup_workspace_folders`
- `list_memory_items`
- `list_memory_review_items`
- `delete_memory_item`
- `propose_rewrite`
- `save_key_memory`
- `list_creative_assets`
- `create_character_asset`
- `create_world_rule`
- `update_creative_asset`
- `delete_creative_asset`
- `delete_creative_assets`
- `list_timeline_events`
- `create_timeline_event`
- `update_timeline_event`
- `reorder_timeline_events`
- `delete_timeline_event`
- `list_character_states`
- `update_character_state`
- `delete_character_state`
- `create_relationship_edge`
- `update_relationship_edge`
- `delete_relationship_edge`
- `list_material_changes`

## Output

Commands support:

- Human-readable output by default.
- `--json` for machine-readable output.
- Clear non-zero exits and concise error messages for HTTP errors.

For streaming Agent messages, the CLI prints streamed text as it arrives and can emit raw event JSON with `--json`.

## Safety

The CLI follows backend safety rules. Destructive or broad mutations require either interactive confirmation or `--yes`.

Examples requiring confirmation:

- Deleting memories, assets, timeline events, character states, relationships, conversations, model profiles.
- Emptying workspace trash.
- Applying `global_replace_keyword` with `dry_run=false`.
- Running bulk delete Agent tools.

Backend confirmation objects remain the source of truth for proposed document writes.

## Testing

Backend tests:

- Tool metadata endpoints list every `get_agent_tools()` entry.
- Tool execution endpoint enforces authentication and novel ownership.
- Tool execution endpoint can run at least one pure tool and one scoped runtime tool.

Go CLI tests:

- Help output exists for every registered command group.
- Every known HTTP route has CLI coverage metadata.
- Every backend Agent tool name returned by a fixture has CLI support through `tools run`.
- Auth token storage and Authorization header behavior.
- JSON body handling, file input, file output, HTTP error formatting.
- Destructive commands require confirmation unless `--yes` is passed.

Manual verification:

```bash
cd cli && go test ./...
cd backend && env PYTHONPATH=. pytest -v tests/test_agent_tool_api.py
ai-story --help
ai-story tools list
ai-story api request GET /health
```

## Decisions

- The config file path follows the OS default config directory returned by Go's standard library.
- Polished convenience commands can be added incrementally after the complete `api` and `tools` coverage layers exist.
