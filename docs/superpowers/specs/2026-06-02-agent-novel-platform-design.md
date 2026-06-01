# Agent Novel Platform Design

Date: 2026-06-02

## Overview

Build an Agent-first novel creation IDE for long-form fiction. Users create a novel project, enter a workspace, and co-create through natural conversation with an Agent. The Agent can discuss characters, worldbuilding, plot, chapter drafts, rewrites, and memory, while the application manages the novel workspace, persistent knowledge, context limits, and safe write operations.

The first version is a usable, extensible multi-user web app deployed with Docker Compose. It should support local accounts, per-user data isolation, configurable model providers, RAG through Milvus, and a LangGraph-based Agent with planning, ReAct-style tool use, and human-in-the-loop confirmation.

## Goals

- Provide a three-pane novel IDE: workspace tree, editor/preview, and Agent chat.
- Let users create a novel manually, then create inside it through natural dialogue.
- Support hidden creative Skills that the Agent selects automatically.
- Preserve long-form continuity through layered memory, not vector search alone.
- Allow AI-assisted paragraph rewrites and chapter generation without unsafe automatic overwrites.
- Support context budget visibility and compression before model context limits become invisible failures.
- Deploy locally with Docker Compose.

## Non-Goals For The First Version

- Full commercial SaaS billing, subscriptions, and operations dashboards.
- Image, PDF, Word, or large binary asset ingestion.
- Fully autonomous generation of an entire book without user steering.
- A separate Rust API service. Python is the first-version backend because LangGraph is central to the product.

## Technology Stack

- Frontend: React, TypeScript, shadcn/ui, assistant-ui, TipTap.
- Backend: Python FastAPI.
- Agent runtime: LangGraph.
- Database: Postgres.
- Vector database: Milvus.
- Deployment: Docker Compose.

The FastAPI backend owns authentication, project data, document CRUD, model profiles, Agent streaming APIs, confirmation actions, and persistence. LangGraph can start in the same backend process as an internal module, but its code should stay isolated enough to become a separate worker later.

## Product Structure

### Workspace

Each user can create novels. A novel opens into a workspace with:

- A left workspace tree for folders, chapters, drafts, and setting documents.
- A center editor and preview area for the active document.
- A right Agent chat area for co-creation.

Documents can represent chapters, drafts, setting notes, or other text assets. Chapters and drafts share editing primitives but may have different statuses such as `draft`, `in_review`, and `final`.

### Editor

The editor uses TipTap and supports:

- Rich text editing.
- Preview mode.
- Autosave.
- Version history.
- Selection-aware AI actions.
- Applying AI-generated replacements after confirmation.

When the user selects text and asks the Agent to rewrite it, the Agent reads the selected text, nearby document context, relevant memories, and the user instruction. It returns a candidate replacement. The user can accept, reject, or ask for another version. Direct replacement is allowed only when the user explicitly grants that action for the current request.

### Agent Chat

The right-side chat uses assistant-ui and supports:

- Streaming Agent responses.
- Plan display.
- Tool call status.
- Retrieved context summaries.
- Human approval cards.
- Error and retry controls.

The conversation is scoped to the current novel. Different novels have separate conversations, memories, documents, and model settings.

## Authentication And Isolation

The first version supports local accounts with email or username plus password. Passwords are hashed server-side. OAuth is not required in the first version, but the data model should leave room for GitHub or Google OAuth identities.

All primary tables include user ownership or enforce ownership through their novel relationship. API requests must filter by authenticated user, and Agent tools must operate only inside the current user's current novel.

## Model Configuration

Models are configured through `ModelProfile` records instead of hard-coded provider assumptions.

The first version includes templates for OpenAI and Anthropic, and supports OpenAI-compatible providers through:

- Base URL.
- API key.
- Chat model.
- Writing model.
- Summary model.
- Embedding model.
- Optional headers.
- Model capabilities.

Model capabilities include:

- Tool calling support.
- JSON mode support.
- Streaming support.
- Context window size.
- Embedding dimensions.

Each novel can choose a default model profile. The Agent uses profile capabilities to decide whether to use native tool calling, structured JSON output, streaming, or fallback prompting.

## Agent Design

The Agent is implemented with LangGraph. It is not a fixed wizard. It is a ReAct-style collaborator that plans, calls tools, presents candidates, and asks for confirmation before persistent writes.

### Agent Loop

For each user message, the Agent:

1. Loads the current workspace context: novel, open document, selected text, recent conversation, and relevant settings.
2. Classifies the user's intent: discussion, worldbuilding, character work, chapter drafting, paragraph rewrite, memory update, directory change, or general question.
3. Builds a context package using the Context Manager.
4. Calls safe read/retrieval tools automatically.
5. Generates a plan when the task is non-trivial.
6. Produces drafts, candidate changes, or confirmation requests.
7. Executes write tools only after user approval or explicit one-time authorization.
8. Records versions, Agent run steps, memory updates, and errors.

### Hidden Creative Skills

Skills are mostly hidden from users. Users talk naturally; the Agent chooses tools.

Core first-version Skills:

- `search_memory`: Search layered memory and Milvus-backed chunks.
- `read_workspace_context`: Read the active novel, tree, document, selected text, and nearby documents.
- `draft_character_card`: Turn discussion into a character card draft.
- `draft_worldbuilding_entry`: Turn discussion into a worldbuilding entry draft.
- `draft_plot_thread`: Draft or update plot threads, conflicts, and foreshadowing.
- `draft_chapter_outline`: Draft chapter goals or outlines.
- `draft_chapter_content`: Draft chapter prose.
- `rewrite_selection`: Rewrite selected text according to the user's instruction.
- `summarize_chapter_memory`: Summarize a completed chapter into events, character states, open questions, and foreshadowing changes.
- `draft_key_memory`: Create a high-priority memory from a user reminder.
- `build_context_pack`: Assemble an inspectable context package for a writing task.
- `propose_workspace_changes`: Propose folder, chapter, and draft changes.
- `commit_confirmed_change`: Persist a confirmed write to documents, assets, memory, or workspace structure.

### Human-In-The-Loop Policy

The Agent may automatically:

- Retrieve memory.
- Read workspace context.
- Estimate context budget.
- Generate plans.
- Generate candidate text.
- Generate draft assets or draft memories.

The Agent must ask for confirmation before:

- Creating or modifying official character cards, worldbuilding entries, plot threads, foreshadowing records, or key memories.
- Writing, replacing, or overwriting document content.
- Applying selected-text rewrites.
- Updating chapter completion memory.
- Creating many chapters or making bulk tree changes.

The Agent requires strong confirmation before:

- Deleting chapters, drafts, assets, or memories.
- Bulk deletion.
- Clearing or rebuilding the vector index.
- Overwriting large document ranges.
- Changing model credentials or global Agent configuration.

## Data Model

Postgres is the source of truth. Milvus is a rebuildable vector index.

Core tables:

- `users`: local account data and OAuth extension fields.
- `model_profiles`: model provider configuration and capabilities.
- `novels`: title, description, owner, default model profile, and writing constraints.
- `workspace_nodes`: tree nodes for folders, chapters, drafts, and setting documents.
- `documents`: document body and metadata.
- `document_versions`: immutable versions for rollback.
- `conversations`: novel-scoped chat threads.
- `messages`: user messages, Agent messages, tool call messages, and confirmation cards.
- `agent_runs`: LangGraph run metadata, status, plan, steps, errors, and checkpoint references.
- `pending_confirmations`: proposed write operations waiting for user approval.
- `creative_assets`: official structured assets such as characters, world rules, locations, organizations, items, plot threads, and foreshadowing.
- `memory_items`: confirmed long-term memories, including key memories, events, chapter summaries, character states, context snapshots, and user preferences.
- `memory_review_items`: Agent-drafted memories waiting for user review before they become official memory.
- `timeline_events`: chapter-ordered events with actors, location, cause, result, and chronology.
- `character_states`: per-character state snapshots after chapters or major events.
- `relationship_edges`: lightweight graph edges between characters, organizations, locations, events, and foreshadowing.
- `context_packs`: assembled context packages for writing tasks.
- `rag_chunks`: vector-indexed chunks with source IDs, hashes, versions, and Milvus vector IDs.

## Layered Memory System

The system should not rely on vector RAG alone. Long-form fiction needs structured continuity, inspectable facts, and explicit user priorities.

### Memory Layers

1. Key memories.
2. Structured creative assets.
3. Character state snapshots.
4. Timeline events.
5. Relationship graph edges.
6. Confirmed chapter summaries and long-term memories.
7. Neighboring chapter context.
8. Vector RAG chunks.
9. Raw conversation history.

Key memories are hard constraints or high-priority reminders created by the user or drafted by the Agent after the user says something like "remember this" or "this is especially important." They are confirmed before becoming official memory. They can be classified as character constraints, world rules, plot prohibitions, style preferences, user preferences, or book-level facts.

High-priority key memories should be loaded by deterministic query and injected into the context pack before vector retrieval results. They are not treated as ordinary RAG chunks because violating them is usually worse than omitting a semantically similar reference.

### Structured Creative Assets

Assets should have both prose descriptions and structured fields. Examples:

- Character: motivation, goal, secret, voice, relationships, current status, forbidden behavior.
- World rule: scope, exceptions, consequences, related locations or organizations.
- Foreshadowing: planted chapter, status, related characters, intended payoff, resolved chapter.
- Plot thread: conflict, stakes, current phase, related events, unresolved questions.

The Agent should query these structured fields directly when possible instead of depending only on semantic similarity.

### Timeline

Each finished chapter can produce timeline events. Events record who did what, where, when in story order, why it mattered, and what changed. New chapter generation can load recent and relevant timeline events to avoid chronology errors.

### Character States

Characters need evolving state. The system stores state snapshots with chapter or event references:

- Location.
- Physical condition.
- Emotional state.
- Goals.
- Knowledge.
- Secrets.
- Relationship changes.
- Open obligations.

When writing a chapter that includes a character, the Agent loads that character's latest relevant state before drafting.

### Relationship Graph

The first version uses a lightweight relationship graph in Postgres. Edges can connect:

- Character to character.
- Character to organization.
- Character to location.
- Event to foreshadowing.
- Plot thread to character.

This helps the Agent retrieve connected context even when the user's prompt does not contain every relevant keyword.

### Context Packs

Before drafting or rewriting important content, the Context Manager builds a `context_pack`. A context pack is an inspectable set of inputs for the current task:

- User instruction.
- Current document and selected text.
- Key memories.
- Relevant characters and latest states.
- Relevant world rules.
- Timeline events.
- Open foreshadowing.
- Neighboring chapter context.
- RAG search results.
- Style guide and constraints.

The Agent can show a summary of the context pack in chat so users know what it is using. Context packs can be saved for debugging, reused, or regenerated.

### Memory Review Queue

Agent-generated summaries, inferred character state changes, extracted world rules, and proposed key memories enter a review queue before becoming official memory. The user can approve, edit, reject, or merge each item. Only approved items become durable memory and receive vector indexing. This prevents mistaken summaries from polluting long-term continuity.

## RAG Strategy

Milvus stores embeddings for confirmed assets, memory items, summaries, and optional document chunks. Every vector chunk keeps metadata:

- User ID.
- Novel ID.
- Source type.
- Source ID.
- Source version.
- Chapter range.
- Character names.
- Asset type.
- Importance.
- Updated time.
- Validity flag.

Writes to official assets or memories update Postgres first, then index or reindex affected chunks. Milvus entries can be marked invalid and rebuilt from Postgres.

Retrieval is weighted by source type:

`key_memory > official_asset > character_state > timeline_event > confirmed_memory > chapter_summary > document_chunk > raw_conversation`

Raw conversation should have low priority and should not become long-term memory unless confirmed or summarized.

## Neighboring Chapter Context

When generating a new chapter, the Agent should include recent chapters as direct context, not only vector search results.

Defaults:

- `recent_chapters_count`: 3.
- `recent_chapter_mode`: compressed text.
- `max_context_tokens`: controlled by model profile and novel settings.

If the model context window is large enough, the Agent can include recent chapter text. If not, it uses compressed chapter text plus summaries and key ending passages. This preserves tone, rhythm, transitions, and emotional continuity better than RAG alone.

## Context Manager

The Context Manager estimates and manages the prompt budget before every Agent run.

It accounts for:

- System and developer instructions.
- User request.
- Current document and selection.
- Neighboring chapters.
- Key memories.
- Structured memory.
- RAG results.
- Recent conversation.
- Tool outputs.
- Response budget.

The chat UI displays context status such as:

- "Context usage is about 62%."
- "Included the previous 3 chapters in compressed form."
- "Recent conversation will be compressed soon."
- "This run used chapter summaries instead of full neighboring chapters."

Thresholds:

- At 70%, warn that compression may happen soon.
- At 85%, automatically compress low-priority context such as old raw conversation or full neighboring chapters.
- At 95%, pause and ask the user to compress or remove context sources.

Compression creates a `context_snapshot` memory item containing:

- Current creative goal.
- Confirmed facts.
- Recent decisions.
- Open questions.
- User preferences.
- Task-relevant details.

Snapshots are stored in Postgres and can be indexed in Milvus when useful.

## Error Handling

- Tool failures appear in chat with step name, error summary, and retry option.
- Invalid structured LLM output is repaired once automatically; repeated failure becomes a user-visible error.
- If Milvus is unavailable, editing and chat continue, but the UI warns that long-term memory search is unavailable.
- If Postgres writes fail, the UI must not claim data was saved.
- AI writes create document versions before applying changes.
- Failed writes do not destroy existing document content.
- Model capability mismatches fall back according to `ModelProfile` and are explained to the user.

## Deployment

Docker Compose services:

- `web`: React application.
- `api`: FastAPI backend with LangGraph module.
- `postgres`: business data, checkpoints, versions, and memory.
- `milvus`: vector database.
- `attu`: optional Milvus admin UI.
- `pgadmin`: optional Postgres admin UI.

MinIO is intentionally excluded from the first version because primary assets are text created through conversation. It can be added later when file and image asset management becomes a priority.

## Testing Strategy

Backend tests:

- Authentication and user isolation.
- Novel, workspace node, document, and version CRUD.
- Confirmation creation, approval, rejection, and expiration.
- Model profile validation.

Agent tests:

- Skill routing from natural language.
- Human-in-the-loop policy enforcement.
- Tool error recovery.
- LangGraph checkpoint persistence and resume.
- Model capability fallback behavior.

Memory tests:

- Key memory creation and priority.
- Structured asset queries.
- Timeline event creation and retrieval.
- Character state updates.
- Relationship edge traversal.
- RAG chunk indexing and invalidation.
- Context pack assembly.

Context tests:

- Token budget estimation.
- Neighboring chapter inclusion.
- Compression thresholds.
- Context snapshot creation.
- UI-facing context status messages.

Frontend tests:

- Workspace tree operations.
- Editor selection integration.
- Confirmation cards.
- Streaming Agent messages.
- Applying and reverting AI document changes.

End-to-end tests:

1. Create an account.
2. Create a novel.
3. Discuss a character with the Agent.
4. Confirm a character card.
5. Add a key memory.
6. Create chapters in the workspace.
7. Generate or rewrite chapter content.
8. Confirm chapter memory.
9. Generate a later chapter using neighboring chapters, structured memory, and RAG.

