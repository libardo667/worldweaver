# Canonical Location Name Enforcement in Action Referee

## Metadata

- ID: 118-canonical-location-enforcement
- Type: minor
- Owner: agent
- Status: backlog
- Risk: low

## Problem

The action referee LLM (Stage A of `/action`) interprets freeform prose and writes location names
as free text. It has no knowledge of the world's canonical location set, so it writes `library`
instead of `library_archive`, `laboratory room` instead of `cryptic_workshop`, etc.

This breaks storylet eligibility for the entire run. A storylet with `requires: {location:
library_archive}` never fires because `location` in state is always a hallucinated variant.
Confirmed in `playtests/agent_runs/20260307t195922z`: `active_storylets_count: 0` on all 20 turns
despite a fully populated storylet DB. Location names in state arc output: `library`, `laboratory`,
`laboratory room`, `cafe corner`, `cryptic basement` — none matching any canonical name.

The fix is harness-side only: inject the canonical location list into the referee prompt so it
maps freeform intent to the nearest canonical name before committing.

## Proposed Solution

When the action referee's Stage A prompt is constructed (in `src/api/game/action.py`), append the
list of canonical location slugs available in the current session's world vars. The referee is
instructed to:

1. If the action involves movement or location change, map to the nearest canonical location name.
2. If no canonical name fits, leave `location` unchanged.
3. Never invent a location name that is not in the canonical list.

The canonical location list is already available in session vars (seeded at bootstrap via
`location_options` or the world schema). It needs to be extracted and injected into the referee
system prompt.

## Files Affected

- `src/api/game/action.py` — Stage A referee prompt construction; inject canonical location list
- `src/services/turn_service.py` — verify where canonical locations are accessible at action time

## Acceptance Criteria

- [ ] Freeform "I head to the library" in a world with `library_archive` writes
      `location=library_archive` to state, not `library`.
- [ ] Freeform actions with no location intent leave `location` unchanged.
- [ ] `active_storylets_count > 0` on at least one turn in a 20-turn location-explorer run with
      canonical locations seeded.
- [ ] `python scripts/dev.py quality-strict` passes.

## Validation Commands

- `python scripts/dev.py quality-strict`
- `python playtest_harness/llm_playtest.py --turns 20 --location-explorer --mom-mode`
- `python playtests/state_arc.py playtests/agent_runs/<run_id>`

## Pruning Prevention Controls

- Authoritative path: `src/api/game/action.py` Stage A referee prompt
- Parallel path introduced: none
- Artifact output target: no generated artifacts
- Default-path impact: core_path (changes Stage A prompt construction on every freeform action)

## Risks and Rollback

- Risk: Canonical list injection slightly increases prompt token count. Acceptable — list is short
  (typically 4–8 locations).
- Rollback: Remove canonical location section from the referee prompt template; no schema changes.
