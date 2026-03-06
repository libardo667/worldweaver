# Unify choice and freeform turn orchestration pipeline

## Problem
Turn execution currently follows two different orchestration paths:

- freeform actions run through staged interpretation/validation/narration (`/action`),
- choice/button progression runs through storylet-next orchestration (`/next`).

This split is functional but creates quality and consistency risk:

- parity drift in validation rigor and diagnostics across turn types,
- harder-to-interpret harness outcomes when action-source mix changes,
- architectural complexity that obscures a single authoritative turn lifecycle.

This especially matters in v3 where consistency across Ack/Commit/Narrate/Hint/Weave is a core vision requirement.

## Proposed Solution
Introduce a shared turn pipeline contract used by both choice and freeform entry points, while preserving route compatibility.

1. Define a common internal turn execution contract:
   - normalized input intent,
   - shared validation and commit boundary,
   - shared diagnostics envelope.
2. Route `/next` choice flow through the same staged/validated orchestration primitives used by `/action` where feasible.
3. Keep route payloads backward compatible:
   - no breaking request/response schema changes,
   - additive diagnostics only.
4. Add explicit turn-mode diagnostics to record:
   - `turn_source` (`choice_button` vs `freeform_action`),
   - `pipeline_mode` (`unified_staged` vs compatibility fallback),
   - validation/commit phase outcomes.
5. Preserve reducer-only canon mutation authority and existing rollback guarantees.

## Files Affected
- `src/services/turn_service.py`
- `src/api/game/orchestration_adapters.py`
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/models/schemas.py`
- `tests/api/test_game_endpoints.py`
- `tests/integration/test_turn_progression_simulation.py`

## Non-Goals
- Replacing existing `/next` or `/action` route contracts.
- Redesigning frontend turn UX in this item.
- Reworking projection planner algorithms.

## Acceptance Criteria
- [ ] Choice and freeform turns share a single authoritative staged orchestration path (or clearly bounded compatibility bridge).
- [ ] Diagnostics expose turn source and pipeline mode for every turn.
- [ ] Reducer/rollback safety remains intact across both turn sources.
- [ ] Existing API consumers remain backward compatible.
- [ ] Integration tests cover parity behavior between choice and freeform flows.

## Validation Commands
- `pytest -q tests/api/test_game_endpoints.py`
- `pytest -q tests/integration/test_turn_progression_simulation.py`
- `python scripts/dev.py quality-strict`

## Risks & Rollback
- Risk: forcing strict parity can temporarily reduce narrative flexibility in one path.
- Risk: migration mistakes could regress route-level behavior relied on by existing clients.

Rollback:
- Keep existing `/next` and `/action` orchestration branches active behind feature flag.
- Disable unified staging path if parity regressions appear, while retaining additive diagnostics.
