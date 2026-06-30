---
name: ai-story-novel-chapter-repair
description: Use when repairing, revising, polishing, diagnosing, or micro-patching existing AI Story novel chapters, especially published chapters, openings, retention problems, weak character entrances, or continuity issues.
---

# AI Story Novel Chapter Repair

Flow skill for existing chapters. It orchestrates atomic novel skills and AI Story tools.

## Required Sub-Skills

- REQUIRED SUB-SKILL: ai-story-local-agent for platform context and write tools.
- REQUIRED SUB-SKILL: ai-story-scoring when scoring, platform risk, retention, or quality is part of the request.
- REQUIRED SUB-SKILL: ai-story-novel-reader-promise for opening, chapter hook, or drop-off diagnosis.
- REQUIRED SUB-SKILL: ai-story-novel-character-entrance when a major character's first impression, heroine presence, clothing, beauty, or relationship signal is weak.
- REQUIRED SUB-SKILL: ai-story-novel-continuity when facts, timeline, power, relationships, or memories may change.

## Repair Orchestration

Use this flow as a dispatcher, not a direct rewrite button.

1. Platform read: load target chapter, adjacent chapter context, novel metadata, relevant memories, timeline, character states, relationships, and recent material changes.
2. Issue Classification: classify the problem before editing. Check reader promise, chapter purpose, hook, character entrance, continuity, plot structure, prose polish, platform risk, and AI-pattern language.
3. Repair Depth: choose micro patch, light revision, or rewrite. Published chapters default to micro patch; drafts may use light revision; rewrite only when the user explicitly asks or the draft is unusable.
4. Sub-Skill Routing: route each issue to its atomic skill: reader promise -> `ai-story-novel-reader-promise`; character entrance -> `ai-story-novel-character-entrance`; continuity -> `ai-story-novel-continuity`; structure/hook -> `ai-story-novel-plot-structure`; prose polish/AI味 -> `ai-story-novel-prose-polish`; scoring/risk -> `ai-story-scoring`.
5. Patch and sync: apply the smallest effective platform edit, then sync material, memory, timeline, relationship, or character-state changes when the patch creates durable facts.

## Workflow

1. Identify status: published chapter, draft, outline, or local cache. Published chapters default to minimal patches.
2. Read platform chapter text and adjacent context. Do not rely on `.store/` unless platform is unavailable.
3. Diagnose before editing: reader promise, chapter purpose, character entrance, continuity, system density, AI-pattern language, and chapter-end hook.
4. Choose repair depth: micro patch, light revision, or rewrite only when the user explicitly wants it or the draft is unpublished.
5. Preserve style-bearing material: concrete dialogue, emotional ambiguity, rhythm, and canon facts.
6. Apply through platform tools such as `propose_selection_replace`, `propose_document_update`, or `write_document_content`.
7. Reconcile platform materials and report what changed.

## Character Presence Gate

For any patch that touches a scene where 主角、女主、反派、关键盟友 or another recurring major character first appears, re-enters the chapter, takes relationship pressure, or becomes newly important, apply `ai-story-novel-character-entrance` before editing. Confirm role, scene relevance, first impression, behavior or voice, and 至少一个外部可记忆标记. Do not leave an important character represented only by name, function, dialogue, or plot position.
