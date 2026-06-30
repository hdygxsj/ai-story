from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

router = APIRouter(tags=["local-novel-skills"])

_COMMON_SETUP = """## Setup

Use AI Story through the Go CLI:

```bash
export AI_STORY_API_BASE="<backend-url>"
export AI_STORY_ACCESS_TOKEN="<access-token>"
ai-story agent manifest
```

Prefer platform data over local caches. Read chapters, materials, timeline, memories, character states, attributes, inventory, maps, relationships, and recent material changes before making story-facing judgments.
"""

LOCAL_NOVEL_SKILLS = {
    "ai-story-novel-topic": f"""---
name: ai-story-novel-topic
description: Use when designing or revising AI Story novel topics, book titles, blurbs, genre positioning, golden fingers, marketable hooks, reader promise, or launch risks.
---

# AI Story Novel Topic

Use this atomic skill to shape a Book pitch without leaving AI Story platform context.

{_COMMON_SETUP}

## Platform Inputs

Read existing novel metadata and comparable in-platform materials before proposing changes:

```bash
ai-story api request GET /novels
ai-story api request GET /novels/{{novel_id}}/creative-assets
ai-story api request GET /novels/{{novel_id}}/memory-items
```

## Topic Checks

- Book pitch: title, one-sentence hook, core promise, target reader, genre surface.
- Golden finger: rule, cost, limitation, discovery rhythm, and why it creates chapters.
- Opening pressure: why the story starts now, what fails if the protagonist delays.
- Market fit: what is familiar enough to enter and fresh enough to continue.
- Platform risk: avoid vague trend copying, protected-IP mimicry, and promises the platform chapters cannot support.

## Output

Return 2-3 pitch options or a repair plan for the current title/description. If accepted, update AI Story with `update_novel` and create durable world/character/memory records only when the user wants the pitch applied.
""",
    "ai-story-novel-outline": f"""---
name: ai-story-novel-outline
description: Use when creating or revising AI Story novel outlines, volume arcs, chapter outlines, story engines, protagonist goals, supporting cast plans, or long-form structure.
---

# AI Story Novel Outline

Use this atomic skill to create a Platform outline that lives in AI Story materials, not in a separate file system.

{_COMMON_SETUP}

## Platform Inputs

```bash
ai-story api request GET /novels/{{novel_id}}/nodes
ai-story api request GET /novels/{{novel_id}}/creative-assets
ai-story api request GET /novels/{{novel_id}}/timeline-events
ai-story api request GET /novels/{{novel_id}}/memory-items
```

## Outline Layers

- Story engine: protagonist, desire, obstacle, cost, why now, action, consequence, next problem.
- Volume arc: stage goal, pressure ladder, reward beat, irreversible turn.
- Six-chapter pack: break balance, act, fail, expand, reward/reveal, new turn.
- Chapter outline: purpose, conflict, POV, scene beats, canon facts, new facts, hook.
- State sync: outline decisions that become canon must be saved to timeline, memory, or materials.

## Output

Produce a compact outline and a list of platform updates needed. Use `create_timeline_event`, `save_key_memory`, `create_world_rule`, or character/material tools when applying accepted outline facts.
""",
    "ai-story-novel-character-management": f"""---
name: ai-story-novel-character-management
description: Use when creating, revising, auditing, or syncing AI Story characters, character cards, states, attributes, relationship edges, goals, secrets, arcs, and agency.
---

# AI Story Novel Character Management

Use this atomic skill when character facts need to be designed or synchronized with platform state.

{_COMMON_SETUP}

## Platform Inputs

```bash
ai-story api request GET /novels/{{novel_id}}/creative-assets
ai-story api request GET /novels/{{novel_id}}/character-states
ai-story api request GET /novels/{{novel_id}}/character-attributes
ai-story api request GET /novels/{{novel_id}}/relationship-edges
ai-story api request GET /novels/{{novel_id}}/memory-items
```

## Character State

For each important character, track what they want, know, misunderstand, hide, fear, owe, and refuse to do. Character state must include current location, physical/emotional condition, relationship pressure, and active goal when relevant.

## Platform Writes

- Create or update a character asset for durable identity and role.
- Use `update_character_state` for current emotional, physical, secret, and location state.
- Use `upsert_character_attribute` for calculable level, ability, rank, resources, or location values.
- Use relationship edge tools for trust, debt, intimacy, rivalry, suspicion, and betrayal.
- Use `save_key_memory` for canon constraints future agents must obey.

Do not let character changes exist only in prose if later chapters depend on them.
""",
    "ai-story-novel-worldbuilding": f"""---
name: ai-story-novel-worldbuilding
description: Use when designing, revising, or syncing AI Story world rules, power systems, factions, maps, locations, items, resources, organizations, and setting constraints.
---

# AI Story Novel Worldbuilding

Use this atomic skill when setting facts must become reusable platform material.

{_COMMON_SETUP}

## Platform Inputs

```bash
ai-story api request GET /novels/{{novel_id}}/creative-assets
ai-story api request GET /novels/{{novel_id}}/map-locations
ai-story api request GET /novels/{{novel_id}}/inventory-items
ai-story api request GET /novels/{{novel_id}}/timeline-events
```

## World Rule

A World rule should answer: what is possible, what is costly, who benefits, who is harmed, how readers see it in action, and what it cannot solve.

## Platform Writes

- Use `create_world_rule` or `update_creative_asset` for rules, factions, systems, and durable setting entries.
- Use `upsert_map_location` for places, parent regions, adjacency, coordinates, and travel constraints.
- Use `upsert_inventory_item` for resources, artifacts, ownership, quantities, and storage.
- Use timeline events when the world fact has history or a reveal order.

Keep worldbuilding scene-facing: each rule should create pressure, choice, obstacle, or reward.
""",
    "ai-story-novel-plot-structure": f"""---
name: ai-story-novel-plot-structure
description: Use when planning, auditing, or repairing AI Story plot arcs, foreshadowing, setup and payoff, chapter hooks, pacing, volume turns, pressure ladders, and scene purpose.
---

# AI Story Novel Plot Structure

Use this atomic skill to manage the Plot contract between setup, pressure, payoff, and next hook.

{_COMMON_SETUP}

## Platform Inputs

```bash
ai-story api request GET /novels/{{novel_id}}/nodes
ai-story api request GET /novels/{{novel_id}}/timeline-events
ai-story api request GET /novels/{{novel_id}}/memory-items
ai-story tools run {{novel_id}} search_documents_by_keyword --arg query=伏笔
```

## Structure Checks

- Every scene segment changes situation, knowledge, relationship, resource, risk, or plan.
- Every setup has a planned pressure or payoff; every payoff has a visible setup.
- Chapter hooks should create a concrete question, threat, choice, debt, reveal, or reward gap.
- Volume pacing alternates pressure, partial reward, consequence, and larger problem.
- Do not solve tension with unexplained power jumps or author convenience.

## Platform Writes

Save durable plot contracts as memories or timeline events. If a plot repair changes canon, update related materials and relationship state.
""",
    "ai-story-novel-reader-promise": f"""---
name: ai-story-novel-reader-promise
description: Use when diagnosing web-novel retention, opening funnels, reader promise mismatch, chapter hooks, title-intro alignment, or why readers drop before continuing.
---

# AI Story Novel Reader Promise

Use this atomic skill to judge whether a chapter gives the reader what the title, intro, genre, and first screen promised.

{_COMMON_SETUP}

## Reader Promise Check

Read the platform novel metadata and target chapters first:

```bash
ai-story api request GET /novels
ai-story api request GET /novels/{{novel_id}}/nodes
ai-story tools run {{novel_id}} score_chapters_with_rubric --arg scope=selected --json-arg node_ids='["chapter-node-id"]'
```

Evaluate:

- Title promise: what does the title make the reader expect in the first screen?
- First-screen delivery: does the opening show the promised conflict, desire, danger, or novelty quickly?
- Chapter purpose: what irreversible change happens by the end?
- Hook chain: does each chapter end with a fresh question, pressure, or choice?
- Explanation load: are system panels, backstory, or rules replacing visible action?
- Reward timing: how many chapters until the core selling point pays off?

## Report Shape

State whether the issue is prose quality, promise mismatch, slow payoff, weak hooks, or platform-risk quality. Give one minimal repair direction per weak chapter. For published chapters, default to entrance and paragraph-level patches rather than structural rewrites.
""",
    "ai-story-novel-character-entrance": f"""---
name: ai-story-novel-character-entrance
description: Use when introducing, repairing, or reviewing major novel characters, heroine presence, beauty writing, clothing, first impressions, relationship tension, or character anchoring.
---

# AI Story Novel Character Entrance

Use this atomic skill when a core character needs stronger first-page presence without becoming a static description card.

{_COMMON_SETUP}

## Hard Rule

Core characters cannot enter naked: a heroine, love interest, rival, villain, or recurring ally needs role, scene relevance, first impression, and at least one external marker the reader can remember.

## Entrance Layers

For important characters, check:

- Role: who is this person in the scene?
- Relevance: why are they here now?
- First impression: what does the POV or room feel before and after they appear?
- Appearance: one or two precise features, not a shopping list.
- Clothing: use fabric, fit, restraint, contrast, trace, or condition to create imagination; avoid inventory-style labels.
- Behavior: posture, gaze, voice, habitual movement, or how they handle pressure.
- Response: another character's reaction can prove beauty or status more naturally than direct praise.
- Agency: what does this person want before the protagonist's plot touches them?

## Beauty And Clothing

When beauty matters, make it do story work:

- Let clothing imply class, self-control, secrecy, vulnerability, rebellion, or daily discipline.
- Keep room for imagination: name a suggestive detail and let the reader complete the image.
- Avoid flat tags such as "校花", "绝美", "身材很好" unless the scene immediately proves them through reaction or consequence.
- Do not over-describe underage school settings. Keep sensuality restrained and age-appropriate.

## Repair Order

Clarify role, then relationship, then first impression, then one memorable visual or behavioral marker. Do not dump biography unless the scene naturally permits it.
""",
    "ai-story-novel-continuity": f"""---
name: ai-story-novel-continuity
description: Use when checking or repairing novel continuity, timeline order, character knowledge, power levels, relationship state, material drift, stale memories, or platform story facts.
---

# AI Story Novel Continuity

Use this atomic skill before changing facts or after prose edits that may affect durable story state.

{_COMMON_SETUP}

## Platform Truth

Use platform truth as the continuity contract.

Platform truth outranks local cache. Gather the current state:

```bash
ai-story api request GET /novels/{{novel_id}}/nodes
ai-story api request GET /novels/{{novel_id}}/creative-assets
ai-story api request GET /novels/{{novel_id}}/timeline-events
ai-story api request GET /novels/{{novel_id}}/memory-items
ai-story api request GET /novels/{{novel_id}}/character-states
ai-story api request GET /novels/{{novel_id}}/character-attributes
ai-story api request GET /novels/{{novel_id}}/inventory-items
ai-story api request GET /novels/{{novel_id}}/map-locations
ai-story api request GET /novels/{{novel_id}}/relationship-edges
ai-story api request GET /novels/{{novel_id}}/material-changes
```

## Checks

- Character knowledge: nobody acts on information they have not learned.
- State carry-forward: injury, location, emotional pressure, alliance, secret, and resource changes persist.
- Timeline: cause precedes effect; travel, recovery, training, and escalation have believable time.
- Power curve: levels and abilities do not inflate for convenience.
- Object state: items cannot be lost, spent, broken, or transferred inconsistently.
- Relationship edge: trust, debt, intimacy, suspicion, and betrayal match prior scenes.
- Promise/payoff: setups are not forgotten, paid off before planted, or repeated without progress.

## After Edits

If prose changes durable facts, update platform materials, memories, timeline, states, attributes, inventory, maps, or relationship edges through Agent tools. If no durable facts changed, say so explicitly.
""",
    "ai-story-novel-prose-polish": f"""---
name: ai-story-novel-prose-polish
description: Use when polishing AI Story novel prose for rhythm, dialogue, pacing, sensory specificity, genre voice, de-AI residue, system-density reduction, or stronger emotional and爽点 delivery.
---

# AI Story Novel Prose Polish

Use this atomic skill for a Polish pass on existing platform prose.

{_COMMON_SETUP}

## Platform Inputs

Read the target document and adjacent chapters before changing style:

```bash
ai-story api request GET /novels/{{novel_id}}/nodes
ai-story tools run {{novel_id}} read_document --arg document_id={{document_id}}
ai-story tools run {{novel_id}} score_chapters_with_rubric --arg scope=selected --json-arg node_ids='["chapter-node-id"]'
```

## Polish Modes

- Light: clarity, rhythm, paragraph breaks, repeated words, dialogue tags.
- Retention: first-screen pressure, shorter explanation, stronger chapter-end hook.
- S爽 point: setup, anticipation, release, witness reaction, consequence.
- De-AI: remove template contrast, generic abstraction, repeated sentence frames, and empty evaluation.

Preserve concrete dialogue, canon facts, ambiguity, and authorial texture. For published chapters, prefer selection-level patches.

## Platform Writes

Use `propose_selection_replace` for precise edits, `propose_document_update` for reviewable full replacements, or `write_document_content` only when direct save is intended. Re-score or re-read after meaningful edits.
""",
    "ai-story-novel-finalize": f"""---
name: ai-story-novel-finalize
description: Use when preparing AI Story novel chapters for publication, checking formatting, typos, platform low-quality risk, sensitive wording, title consistency, chapter order, and final release readiness.
---

# AI Story Novel Finalize

Use this atomic skill for a Publish check before chapters leave the AI Story workspace.

{_COMMON_SETUP}

## Platform Inputs

```bash
ai-story api request GET /novels/{{novel_id}}/nodes
ai-story tools run {{novel_id}} score_chapters_with_rubric --arg scope=selected --json-arg node_ids='["chapter-node-id"]'
ai-story api request GET /novels/{{novel_id}}/material-changes
```

## Publish Check

- Formatting: chapter order, title, paragraph readability, no accidental notes or placeholders.
- Quality: no synopsis-like writing, empty water, repeated template ending, or low-effort batch feel.
- Continuity: chapter facts match platform memories, materials, states, attributes, and timeline.
- Risk: sensitive wording, protected-IP imitation, adult/underage boundary issues, platform low-quality indicators.
- Release note: what changed, what remains risky, and whether more platform sync is needed.

## Platform Writes

Only write fixes through platform document tools. If finalization adds no durable facts, state that material sync is not needed.
""",
    "ai-story-novel-market-radar": f"""---
name: ai-story-novel-market-radar
description: Use when adapting AI Story novels to platform taste, male or female channel expectations, title and intro packaging, trope fit, hot-meme usage, comments, short-video copy, or trend-sensitive market positioning.
---

# AI Story Novel Market Radar

Use this atomic skill for Platform radar while keeping the actual story grounded in AI Story canon.

{_COMMON_SETUP}

## Freshness Rule

Trends, rankings, platform taste, and meme language change quickly. If the user asks for current market judgment, browse fresh sources before making claims. If browsing is not needed, frame guidance as craft heuristics rather than current ranking facts.

## Radar Checks

- Genre surface: title, intro, tags, first-screen promise, and reader expectation.
- Male-channel fit: goal pressure,爽点 rhythm, capability growth, threat clarity, payoff timing.
- Female-channel fit: agency, relationship pressure, status gap, family/social constraint, emotional rhythm.
- Meme use: keep hot language in side banter, comments, captions, or marketing copy unless it fits character voice.
- Platform safety: do not chase trends by copying protected IP, specific living people, or rank-list prose.

## Platform Writes

Apply accepted positioning through `update_novel`, memories, or materials. Do not alter chapter canon for packaging unless the user asks for a chapter revision.
""",
    "ai-story-novel-new-book-start": f"""---
name: ai-story-novel-new-book-start
description: Use when starting a new AI Story novel, setting up a book concept, first three chapters, story bible, initial characters, world rules, timeline, memory, and launch package.
---

# AI Story Novel New Book Start

Use this flow skill for a New book flow inside AI Story.

{_COMMON_SETUP}

## Required Sub-Skills

- REQUIRED SUB-SKILL: ai-story-novel-topic for title, pitch, genre promise, and opening risk.
- REQUIRED SUB-SKILL: ai-story-novel-outline for story engine, volume arc, and first chapter pack.
- REQUIRED SUB-SKILL: ai-story-novel-character-management for core cast, goals, secrets, and states.
- REQUIRED SUB-SKILL: ai-story-novel-worldbuilding for rules, locations, factions, and resources.
- REQUIRED SUB-SKILL: ai-story-novel-reader-promise for first-screen promise and early retention.

## Workflow

1. Build or revise the book pitch.
2. Create platform materials for core characters and world rules.
3. Save launch constraints as memory.
4. Create timeline events for opening arc milestones.
5. Draft first chapter task cards before prose.
6. Use `create_chapter_with_content` only after canon anchors are clear.

Keep all durable setup inside AI Story platform records so future agents can read it.
""",
    "ai-story-novel-chapter-repair": f"""---
name: ai-story-novel-chapter-repair
description: Use when repairing, revising, polishing, diagnosing, or micro-patching existing AI Story novel chapters, especially published chapters, openings, retention problems, weak character entrances, or continuity issues.
---

# AI Story Novel Chapter Repair

Use this flow skill for existing chapters. It orchestrates atomic novel skills and AI Story platform tools.

{_COMMON_SETUP}

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
4. Choose repair depth:
   - Micro patch: opening lines, one entrance, a bridge paragraph, or a hook.
   - Light revision: paragraph order, compressed explanation, stronger action/reaction.
   - Rewrite: only when the user explicitly wants it or the draft is not published.
5. Preserve style-bearing material: concrete dialogue, emotional ambiguity, rhythm, and canon facts.
6. Apply through platform tools such as `propose_selection_replace`, `propose_document_update`, or `write_document_content` according to user intent.
7. Reconcile platform materials and report what changed.

## Output

Lead with findings, then the exact repair direction. If editing, report chapter/document touched, durable facts changed, and whether material/memory/timeline updates were needed.

## Character Presence Gate

For any patch that touches a scene where 主角、女主、反派、关键盟友 or another recurring major character first appears, re-enters the chapter, takes relationship pressure, or becomes newly important, apply `ai-story-novel-character-entrance` before editing. Confirm role, scene relevance, first impression, behavior or voice, and 至少一个外部可记忆标记. Do not leave an important character represented only by name, function, dialogue, or plot position.
""",
    "ai-story-novel-new-chapter": f"""---
name: ai-story-novel-new-chapter
description: Use when planning, drafting, continuing, or creating a new AI Story novel chapter from platform context, outline, prior chapters, materials, timeline, and memories.
---

# AI Story Novel New Chapter

Use this flow skill when creating new chapter prose inside AI Story.

{_COMMON_SETUP}

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

- Previous chapter handoff:
- POV and location:
- Chapter goal:
- Core conflict:
- Reader promise / reward:
- Characters and what each wants:
- Information boundary:
- Required canon facts:
- New durable facts expected:
- Scene beats:
- Chapter-end hook:

If the user asks to move fast, create the card internally but still obey it.

## Drafting Rules

- Every scene segment must change the situation.
- Action should reveal setting, relationship, and stakes, not just move bodies.
- System panels and exposition must not replace visible pressure.
- Major character entrances need role, relevance, first impression, and a memorable marker.
- Keep power growth earned and state changes durable.

## Character Presence Gate

Before drafting prose, list every 主角、女主、反派、关键盟友 or recurring major character who first appears, re-enters the chapter, takes relationship pressure, or becomes newly important in this chapter. For each one, apply `ai-story-novel-character-entrance` and ensure role, scene relevance, first impression, behavior or voice, and 至少一个外部可记忆标记 are present in prose. Do not let a major character enter as only a name, function, dialogue source, or plot marker.

## Write And Sync

Create the chapter with `create_chapter_with_content` or update a provided document with `write_document_content`. After writing, update memories, materials, character states, attributes, inventory, maps, relationships, and timeline entries that changed. If nothing changed beyond prose, state that explicitly.
""",
    "ai-story-novel-pre-publish-check": f"""---
name: ai-story-novel-pre-publish-check
description: Use when running a pre-publication AI Story chapter or batch check for quality, retention, continuity, formatting, platform risk, and final micro-fixes.
---

# AI Story Novel Pre-Publish Check

Use this flow skill for a Pre-publish flow before release.

{_COMMON_SETUP}

## Required Sub-Skills

- REQUIRED SUB-SKILL: ai-story-scoring for rubric and platform-risk scoring.
- REQUIRED SUB-SKILL: ai-story-novel-reader-promise for hook and retention.
- REQUIRED SUB-SKILL: ai-story-novel-continuity for canon sync.
- REQUIRED SUB-SKILL: ai-story-novel-prose-polish for final prose.
- REQUIRED SUB-SKILL: ai-story-novel-finalize for publish formatting and risk.

## Workflow

1. Read selected platform chapters and neighboring context.
2. Score selected chapters with rubric.
3. Check reader promise, chapter-end hook, and system/explanation density.
4. Check durable facts against materials, memories, states, attributes, relationships, and timeline.
5. Apply only necessary micro-fixes through platform document tools.
6. Report pass/fail, remaining risks, and whether platform material sync changed.
""",
    "ai-story-novel-volume-review": f"""---
name: ai-story-novel-volume-review
description: Use when reviewing an AI Story volume, arc, or chapter range for pacing, continuity, setup payoff, character arcs, reader promise, weak chapters, and next-volume planning.
---

# AI Story Novel Volume Review

Use this flow skill for Volume review across a chapter range.

{_COMMON_SETUP}

## Required Sub-Skills

- REQUIRED SUB-SKILL: ai-story-scoring for range scoring.
- REQUIRED SUB-SKILL: ai-story-novel-plot-structure for arc, setup/payoff, and pressure ladder.
- REQUIRED SUB-SKILL: ai-story-novel-character-management for character arc and relationship movement.
- REQUIRED SUB-SKILL: ai-story-novel-continuity for platform state drift.
- REQUIRED SUB-SKILL: ai-story-novel-outline for next arc repair or planning.

## Workflow

1. Read node list and target chapter range from platform.
2. Score the range and identify weak chapters, repeated issues, and high-risk sections.
3. Map arc movement: promise, pressure, reward, cost, turn.
4. Check character and relationship changes against platform states.
5. Produce a repair queue: micro patches, light rewrites, material sync, next-volume setup.
6. Save accepted durable conclusions as memories or timeline events.
""",
    "ai-story-novel-workflow": f"""---
name: ai-story-novel-workflow
description: Use when choosing or orchestrating AI Story novel skills for end-to-end writing, repair, scoring, outlining, publishing, volume review, character, world, market, or continuity work.
---

# AI Story Novel Workflow

Use this Workflow router when the task spans multiple novel operations.

{_COMMON_SETUP}

## Route By User Intent

- New idea, title, intro, sell point: use ai-story-novel-topic.
- New book setup: use ai-story-novel-new-book-start.
- Outline, volume, chapter cards: use ai-story-novel-outline and ai-story-novel-plot-structure.
- New chapter: use ai-story-novel-new-chapter.
- Existing chapter repair: use ai-story-novel-chapter-repair.
- Female lead, appearance, clothing, entrance: use ai-story-novel-character-entrance and character-management.
- World rule, map, faction, item: use ai-story-novel-worldbuilding.
- Continuity drift: use ai-story-novel-continuity.
- Prose, rhythm,爽点, de-AI: use ai-story-novel-prose-polish.
- Current platform taste or packaging: use ai-story-novel-market-radar.
- Release readiness: use ai-story-novel-pre-publish-check.
- Arc/range diagnosis: use ai-story-novel-volume-review.

## Flow Discipline

After routing, execute the selected flow skill's sequence. A route is not enough.

- Existing chapter repair: follow the repair flow sequence: platform read, Issue Classification, Repair Depth, Sub-Skill Routing, patch, then platform sync; do not skip straight to prose.
- New chapter: follow the new chapter flow sequence: platform read, task card, Preflight Gates, Draft Sequence, then Post-Write Sync; do not skip straight to prose.
- Multi-issue requests: run the main flow first, then call atomic skills only at their required decision points.

## Platform Boundary

Always start from AI Story platform routes and tools. Do not invent a separate source of truth. Any accepted durable fact must be written back through platform tools or explicitly left as advice only.
""",
}


@router.get("/local-novel-skills")
async def list_local_novel_skills() -> dict[str, list[dict[str, str]]]:
    return {
        "skills": [
            {"name": name, "path": f"/local-novel-skills/{name}/SKILL.md"}
            for name in sorted(LOCAL_NOVEL_SKILLS)
        ]
    }


@router.get("/local-novel-skills/{skill_name}/SKILL.md")
async def download_local_novel_skill(skill_name: str) -> Response:
    skill = LOCAL_NOVEL_SKILLS.get(skill_name)
    if skill is None:
        raise HTTPException(status_code=404, detail="Unknown local novel skill")
    return Response(skill, media_type="text/markdown; charset=utf-8")
