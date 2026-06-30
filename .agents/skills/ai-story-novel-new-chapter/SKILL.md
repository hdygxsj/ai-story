---
name: ai-story-novel-new-chapter
description: Use when planning, drafting, continuing, or creating a new AI Story novel chapter from platform context, outline, prior chapters, materials, timeline, and memories.
---

# AI Story Novel New Chapter

Flow skill for creating new chapter prose inside AI Story.

## Required Sub-Skills

- REQUIRED SUB-SKILL: ai-story-local-agent for platform context, writing tools, and post-write material updates.
- REQUIRED SUB-SKILL: ai-story-novel-reader-promise for chapter purpose, pressure, reward timing, and chapter-end hook.
- REQUIRED SUB-SKILL: ai-story-novel-character-entrance when introducing or re-centering major characters.
- REQUIRED SUB-SKILL: ai-story-novel-continuity before and after writing.

## New Chapter Orchestration

Use this flow as a sequence. Do not jump from a user request directly to prose.

1. Platform read: load previous chapter, next constraints if known, outline, active characters, current states, relationships, timeline, memories, and relevant materials.
2. Chapter task card: lock POV, location, chapter goal, core conflict, reader reward, active characters and wants, information boundary, required canon facts, expected durable facts, scene beats, and chapter-end hook.
3. Preflight Gates: pass the reader promise gate, character presence gate, continuity gate, and scene purpose gate before drafting.
4. Draft Sequence: write visible pressure first, make action reveal setting and relationship, keep exposition under scene pressure, place reward or reversal, and end with a concrete next question.
5. Post-Write Sync: update memories, timeline, character states, relationships, materials, inventory, maps, and attributes changed by the new prose. If nothing changed beyond prose, state that explicitly.

## Context Load

Read near-field full text first: previous chapter, target outline if present, next known constraints, active characters, current states, timeline, memories, and relationships. Expand only when a continuity dependency requires it.

## Chapter Task Card

Build a Chapter task card before prose so the chapter has a clear job.

Before drafting, lock a compact task card:

- Previous chapter handoff
- POV and location
- Chapter goal
- Core conflict
- Reader promise / reward
- Characters and what each wants
- Information boundary
- Required canon facts
- New durable facts expected
- Scene beats
- Chapter-end hook

If the user asks to move fast, create the card internally but still obey it.

## Character Presence Gate

Before drafting prose, list every 主角、女主、反派、关键盟友 or recurring major character who first appears, re-enters the chapter, takes relationship pressure, or becomes newly important in this chapter. For each one, apply `ai-story-novel-character-entrance` and ensure role, scene relevance, first impression, behavior or voice, and 至少一个外部可记忆标记 are present in prose. Do not let a major character enter as only a name, function, dialogue source, or plot marker.

## Write And Sync

Create the chapter with `create_chapter_with_content` or update a provided document with `write_document_content`. After writing, update memories, materials, character states, attributes, inventory, maps, relationships, and timeline entries that changed.
