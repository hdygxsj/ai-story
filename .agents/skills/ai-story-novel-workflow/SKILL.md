---
name: ai-story-novel-workflow
description: Use when choosing or orchestrating AI Story novel skills for end-to-end writing, repair, scoring, outlining, publishing, volume review, character, world, market, or continuity work.
---

# AI Story Novel Workflow

Workflow router for AI Story novel work.

Route by intent: topic for title/pitch, new-book-start for launch setup, outline and plot-structure for arcs, new-chapter for drafting, chapter-repair for existing prose, character-entrance and character-management for heroine or cast issues, worldbuilding for setting, continuity for drift, prose-polish for style, market-radar for packaging, pre-publish-check for release, and volume-review for chapter ranges.

## Flow Discipline

After routing, execute the selected flow skill's sequence. A route is not enough.

- Existing chapter repair: follow the repair flow sequence: platform read, Issue Classification, Repair Depth, Sub-Skill Routing, patch, then platform sync; do not skip straight to prose.
- New chapter: follow the new chapter flow sequence: platform read, task card, Preflight Gates, Draft Sequence, then Post-Write Sync; do not skip straight to prose.
- Multi-issue requests: run the main flow first, then call atomic skills only at their required decision points.

Always start from AI Story platform routes and tools. Accepted durable facts must be written back through platform tools or explicitly left as advice only.
