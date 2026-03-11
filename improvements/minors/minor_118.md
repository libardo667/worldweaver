# Canonical Location Name Enforcement in Action Referee

## Metadata

- ID: 118-canonical-location-enforcement
- Type: minor
- Owner: agent
- Status: backlog
- Risk: low

## Problem

The action referee LLM (Stage A of `/action`) interprets freeform prose and writes location names
as free text. It has no knowledge of the world's canonical location set.

With the SF city pack now seeding the world graph (71 neighborhoods, BART/Muni stops, key
landmarks), canonical location names are real place names — "The Mission", "16th St BART Station",
"Dolores Park" — but Stage A still writes whatever the model infers from the action text. This
means a player saying "I walk over to Dolores" might stamp `location=Dolores` instead of
`location=Dolores Park`, drifting from the canonical node name and potentially breaking co-location
detection, roster tracking, and chat scoping.

Note: `_detect_movement_intent` in `command_interpreter.py` already fuzzy-matches against the
location graph with a 0.6 threshold and handles many cases. The remaining gap is Stage A's
`intent_delta` — when movement intent slips through as a state delta rather than being caught by
the pre-movement detector, it still writes free-text names.

## Proposed Solution

When the action referee's Stage A prompt is constructed, inject the list of canonical location
names from the world graph (via `world_memory.get_location_graph()`). The referee is instructed to:

1. If the action involves movement, map the destination to the nearest canonical location name.
2. If no canonical name fits closely, omit the location delta entirely — let the pre-movement
   detector handle it or leave location unchanged.
3. Never invent a location name that isn't in the canonical list.

The canonical list comes from `WorldNode` records (type=location), not from session vars — so it
reflects the live city pack graph rather than a static bootstrap artifact.

## Files Affected

- `src/services/command_interpreter.py` — Stage A referee prompt construction; inject canonical
  location list from world graph
- `src/services/world_memory.py` — confirm `get_location_graph()` is accessible at action time
  (it already is)

## Acceptance Criteria

- [ ] Freeform "I walk to Dolores Park" writes `location=Dolores Park` (canonical node name),
      not a hallucinated variant.
- [ ] Freeform actions with no movement intent leave `location` unchanged.
- [ ] Co-located character roster is stable across turns where the player moves by freeform action.
- [ ] `python scripts/dev.py quality-strict` passes.

## Validation Commands

- `python scripts/dev.py quality-strict`
- Manual: take 5–10 freeform movement actions in the SF world; inspect `player_location` in
  digest response; confirm names match city pack node names exactly.

## Pruning Prevention Controls

- Authoritative path: `src/services/command_interpreter.py` Stage A referee prompt
- Parallel path introduced: none
- Default-path impact: core_path (changes Stage A prompt on every freeform action)

## Risks and Rollback

- Risk: City pack has 100+ location nodes — injecting all of them would bloat the prompt. Mitigation:
  inject only the 20–30 nodes nearest to the player's current location (graph neighbors + neighbors
  of neighbors), not the full list.
- Rollback: Remove canonical location section from the referee prompt; no schema or DB changes.
