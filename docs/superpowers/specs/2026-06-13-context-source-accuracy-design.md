# Context Source Accuracy Design

## Goal

Make the Agent context indicator reflect visible, active novel data without repeated source chips or duplicate structured data.

## Confirmed Behavior

- Context source chips are grouped by source and show a count instead of rendering one chip per item.
- Structured assets are loaded deterministically and excluded from RAG search results to avoid injecting the same data twice.
- Documents whose workspace node is in the recycle bin are excluded from neighboring chapter context and RAG search.
- When an Agent tool writes creative assets, timeline events, character states, or relationships, the workspace refreshes those collections so the material and timeline pages match persisted data.

## Boundaries

- Existing stored material and timeline records remain unchanged.
- Existing RAG rows are not migrated or deleted; query-time filtering makes inactive or duplicate sources harmless.
- Context token accounting remains item-based on the backend. Only the UI presentation is grouped.

## Verification

- Backend tests cover RAG source exclusion and trashed document filtering.
- Frontend tests cover grouped context chips and post-Agent material refresh.
- Relevant backend and frontend test suites pass, followed by a frontend build.
