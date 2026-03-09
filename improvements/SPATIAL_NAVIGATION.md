# Spatial Navigation Graph — V4 Design

## Problem

Location transitions are currently LLM-gated. When a player types "go to the
Silt Flats," the intent-extraction stage asks the LLM to evaluate plausibility
and set `delta.location`. This works unreliably: the LLM sometimes rejects valid
destinations, invents location names, or silently ignores the movement entirely.

The root cause is a category error. **Movement is not a creative decision.** It is
a graph traversal. The LLM's job is to narrate what happens at a location — not
to decide whether you can reach it.

---

## Core Concept

The world maintains a **location graph**: nodes are named places, edges are known
paths between them. The graph starts from the world bible (seeded at world
creation) and grows organically as the LLM mentions new places in its narrative
output.

Three rules:

1. **Movement is deterministic.** "Go to X" → look up X in the graph → if X is a
   known node, set `location = X` before the LLM sees the action. The LLM narrates
   the arrival. `plausible` is forced true. No debate.

2. **The graph grows from narration.** After every LLM narrative response, a
   lightweight extraction pass scans the text for location names. New names not
   yet in the graph are added as nodes. Two places mentioned together in the same
   scene get an edge drawn between them.

3. **Exploration is discovery.** A character cannot move to a place that has never
   been mentioned. The geography of the world is only as large as the LLM has
   described it. Agents wandering and describing new places literally build the map.

---

## What Already Exists

The DB already has `WorldNode` and `WorldEdge` tables used for the character/faction
fact graph. Location nodes are a natural extension of the same structure:

- `WorldNode(entity_key="location:silt_flats", entity_type="location", label="Silt Flats", ...)`
- `WorldEdge(from_key="location:cistern_base", to_key="location:silt_flats", relation="path", ...)`

No new tables needed. The existing graph machinery handles storage. What's needed
is a `location:`-namespaced layer on top of it.

---

## Architecture

### 1. Seed from World Bible (at world creation)

When `POST /api/world/seed` generates the world bible, extract all location names
and write them as `WorldNode` records immediately. Draw edges between all bible
locations (they're all considered reachable from each other at start — the graph
can be refined as play continues).

This ensures the location graph is never empty. Even before any agent takes a
turn, the custom character entry screen and agent skills can query real locations.

### 2. Post-Narration Extraction (every turn)

After `render_validated_action_narration` returns narrative text, run a fast
extraction pass:

```
extract_location_mentions(narrative_text, world_id, current_location, db)
```

This is a post-commit side effect — it cannot block the turn response.

#### Deduplication pipeline (critical)

The LLM produces variants across turns: "the old cistern," "Cistern Base,"
"that underground cistern" — all the same place. Naive insertion destroys the
graph. The extraction pass must deduplicate before any write:

1. **Canonical-first match**: World bible names are ground truth. Match extracted
   strings against bible names first (case-insensitive, article-stripped — "the",
   "a", "an" removed). If it matches, use the canonical name. Do not add a node.

2. **Fuzzy match against existing nodes**: Strings that don't exact-match the
   bible are compared against all existing location node labels using token-overlap
   or edit distance. Similarity ≥ 0.8 → treat as the same node, update edge if
   needed.

3. **New-node skepticism**: Strings that don't match anything existing require a
   confidence threshold before insertion. A string must appear in at least 2
   separate narrative outputs before becoming a permanent node. Single-mention
   references ("somewhere south," "a place he used to know") are discarded.

4. **Canonical key / display label separation**: The node key is a stable slug
   (`location:cistern_base`). The display label is whatever canonical form the
   world bible uses ("Cistern Base"). Variant strings from LLM output never
   become keys — they are matched, resolved, and discarded.

No LLM call in this pipeline. Pure string matching and fuzzy comparison only.

### 3. Movement Pre-Check (in `process_turn`)

Before Stage A (intent extraction), inspect the raw action text:

```python
movement_target = _detect_movement_intent(action_text, known_location_names)
```

`_detect_movement_intent` is a simple regex/keyword check ("go to", "walk to",
"head to", "make my way to", "return to", etc.) followed by fuzzy-matching the
remainder against the location graph.

If a match is found:
- Force `delta.set["location"] = matched_location_name` into the committed deltas.
- Set a flag `movement_resolved = True` that Stage A can read.
- Stage A skips movement plausibility entirely for this turn.
- Stage B (narration) receives a hint: `resolved_movement_target = "Silt Flats"`.
  The narration prompt instructs: "The player has moved to {target}. Narrate the
  arrival."

If no match is found (action is not movement, or destination is unknown): normal
pipeline. The LLM may still write a location transition if it chooses; the
extraction pass will pick it up afterward.

### 4. Location Graph API

```
GET /api/world/{world_id}/locations/graph
```

Returns:
```json
{
  "nodes": [
    {"name": "Cistern Base", "key": "location:cistern_base", "description": "..."},
    {"name": "Silt Flats",   "key": "location:silt_flats",   "description": "..."}
  ],
  "edges": [
    {"from": "location:cistern_base", "to": "location:silt_flats", "relation": "path"}
  ]
}
```

Used by:
- Agents to know what's reachable before deciding where to go.
- The Constellation view to render the map.
- The entry screen (already partially solved — entry now gets `locations` from the
  world bible; after this feature lands, it comes from the live graph instead).

### 5. Digest Update

`GET /api/world/digest` adds an `edges` field alongside `locations`:

```json
"edges": [
  {"from": "Cistern Base", "to": "Silt Flats"},
  {"from": "Silt Flats",   "to": "The Green Canal"}
]
```

The frontend Constellation view uses this to render connections, not just a flat
inhabitant list.

---

## Constellation View

The right sidebar evolves from a flat roster into a spatial map:

**Now**: Flat list of location names with inhabitant counts.

**After**: Graph of nodes (locations) and edges (paths), with inhabitant dots at
their current node. The player's own node is highlighted. Adjacent nodes are
visually distinct from distant ones. This doesn't need to be a force-directed
graph — even a simple linear or hub-and-spoke layout is a meaningful improvement.

The Constellation tab already has this name for a reason. The view should feel
like a star chart of the world, not a leaderboard.

---

## Agent Skill Update

`openclaw_entities/template/skills/worldweaver-player.md` gets a new section:

### Perceiving the Location Graph

```bash
WORLD_ID=$(cat $ENTITY_DIR/world_id.txt)
curl -s "http://localhost:8000/api/world/${WORLD_ID}/locations/graph" | python3 -m json.tool
```

This gives you the full list of known places and the paths between them.

### Moving Between Locations

Movement to any node in the graph always succeeds — do not hedge or second-guess
it. Just act:

```
"action": "I walk south toward the Silt Flats."
```

The server resolves the destination. The LLM narrates the arrival.

### Discovering New Places

If a location is mentioned in narrative but you haven't moved there yet, it exists
in the world — you just haven't been there. Moving toward a rumored place is always
worth trying.

---

## Rollout Plan

### Phase 0: Seed graph from world bible (no behavior change)

At seed time, write all bible locations as `WorldNode` records with `entity_type="location"`.
Write edges between all of them. Update `GET /api/world/{world_id}/locations/graph`
to serve these.

Entry screen immediately gets real world-specific locations (this partially already
works via the `entry.locations` fix, but this makes it graph-backed and persistent).

### Phase 1: Post-narration extraction

Add `extract_location_mentions()` as a side-effect call in the turn pipeline,
after narration commits. Nodes and edges accumulate as agents play. No behavior
change to movement yet.

Validation: after 10 agent turns, run `/locations/graph` and verify the graph has
grown beyond the bible seed.

### Phase 2: Movement pre-check

Add `_detect_movement_intent()` before Stage A. Wire resolved movement into the
delta before LLM sees the action. Add narration hint for arrivals.

Validation: "go to [known location]" consistently sets `state_changes.location`
in the API response.

### Phase 3: Constellation graph view

Update the digest endpoint to include edges. Update the frontend Constellation
sidebar to render a graph layout instead of a flat list.

---

## Non-Goals

- **Pathfinding through intermediate nodes.** If A→B→C exists and you say "go to
  C" from A, this does not auto-traverse B. One hop per turn. Multi-hop is a
  future concern.
- **Blocking movement to non-adjacent nodes.** Initially, any known node is
  reachable (the graph is fully connected at world creation). Adjacency constraints
  can be added later as the world grows and geography becomes meaningful.
- **Real-time map rendering.** A static SVG or CSS-positioned layout is fine for
  V4. Force-directed physics or interactive panning is V5+.
- **LLM-assisted edge inference.** The extraction pass uses string matching, not
  another LLM call. Speed matters here — it runs on every turn.

---

## Relation to V4 Milestones

This design is a component of **V4 M1 (Shared World State)**. The location graph
is shared world state — it belongs to the world, not any session. It satisfies
the M1 requirement that "WorldState" (including locations) be world-scoped rather
than session-scoped.

It also directly unblocks **V4 M5 (Multiplayer)**: location-scoped event queries
require a reliable location graph to answer "who is at the same node as me."
