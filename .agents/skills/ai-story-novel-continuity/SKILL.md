---
name: ai-story-novel-continuity
description: Use when checking or repairing novel continuity, timeline order, character knowledge, power levels, relationship state, material drift, stale memories, or platform story facts.
---

# AI Story Novel Continuity

Atomic skill for keeping AI Story platform facts synchronized with prose.

## Setup

Use platform truth as the continuity contract. Platform truth outranks local cache. Gather current state:

```bash
ai-story agent manifest
ai-story api request GET /novels/{novel_id}/nodes
ai-story api request GET /novels/{novel_id}/creative-assets
ai-story api request GET /novels/{novel_id}/timeline-events
ai-story api request GET /novels/{novel_id}/memory-items
ai-story api request GET /novels/{novel_id}/character-states
ai-story api request GET /novels/{novel_id}/character-attributes
ai-story api request GET /novels/{novel_id}/inventory-items
ai-story api request GET /novels/{novel_id}/map-locations
ai-story api request GET /novels/{novel_id}/relationship-edges
ai-story api request GET /novels/{novel_id}/material-changes
```

## Checks

Check character knowledge, state carry-forward, timeline, power curve, object state, relationship edge, and promise/payoff ordering. Nobody should act on information they have not learned, and no state change should live only in prose if later agents need it.

## After Edits

If prose changes durable facts, update platform materials, memories, timeline, states, attributes, inventory, maps, or relationship edges through Agent tools. If no durable facts changed, say so explicitly.
