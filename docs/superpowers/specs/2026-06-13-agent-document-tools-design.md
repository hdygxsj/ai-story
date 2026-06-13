# Agent Document Tools Design

## Scope

The first delivery closes the Agent document-write loop without adding the broader story-bible CRUD or creative skills. It adds scoped document proposals, document-version reads and restores, and workspace-node restoration.

## Safety Model

- Runtime tools are bound to the authenticated user and current novel. Model-supplied IDs are always checked against that scope.
- Creating a new chapter remains an immediate write.
- Replacing a selection, replacing full document content, and restoring a version create `PendingConfirmation` rows.
- Every confirmed document mutation stores the previous body as a `DocumentVersion` before changing the document.
- Confirmation payloads carry the document `updated_at` value observed while proposing. Approval returns HTTP 409 if the document changed in the meantime.
- Workspace restoration is immediate because it only reverses a soft-delete status and does not overwrite prose.

## Components

### Document action service

A focused service owns document lookup, ownership checks, text conversion, proposal creation, optimistic concurrency validation, version creation, mutation, and RAG reindexing. API routes and Agent tools call this service instead of duplicating write logic.

### Runtime tools

- `propose_document_update(document_id, content)` proposes replacement of the full document.
- `propose_selection_replace(document_id, selected_text, replacement_text)` proposes replacement of one uniquely matching text selection.
- `list_document_versions(document_id)` returns accessible versions.
- `propose_version_restore(document_id, version_id)` proposes restoring one version.
- `restore_workspace_node(node_id)` restores a trashed node in the current novel.

The runtime injects `owner_id` and `novel_id`; neither is selected by the model.

### Confirmation execution

Approval dispatches by `action_type`: `document_update`, `selection_replace`, or `version_restore`. The service rechecks scope, pending state, expected timestamp, referenced selection/version, then performs the write atomically. Rejection only resolves the confirmation.

## API And UI Flow

Approval responses include an optional `document_id`, allowing the workspace to reload the active editor after a successful document mutation. Existing confirmation presentation remains usable; the Agent completion and approval paths trigger the existing workspace refresh callback.

## Errors

- Missing or out-of-scope documents, nodes, and versions return 404.
- Already resolved confirmations and stale document proposals return 409.
- Selection replacement returns 409 when the selected text is absent or occurs more than once.
- Invalid restoration of an active node returns 409.

## Tests

Backend tests cover scoped tool access, proposal persistence, stale confirmation rejection, selection-only replacement, version listing/restoration, and node restoration. Frontend tests cover refreshing document state after an approved document confirmation.
