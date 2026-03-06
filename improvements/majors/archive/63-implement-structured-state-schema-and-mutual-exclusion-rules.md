# Major 63: Implement structured state schema and mutual exclusion rules

## Problem Statement
The game state currently relies on dozens of ad-hoc boolean flags, unstructured strings, and numeric trackers that can grow without bounds or conceptually conflict (e.g. a player being simultaneously `hiding` and `negotiating`). This "leaky, redundant" state causes the LLM to lose focus on the core narrative physics, creating a dreamlike, inconsistent experience. The authoritative reducer (Major 59) laid the groundwork; we now need a formal schema to enforce world rules.

## Proposed Solution
Replace the sprawling freeform variables with 3-5 structured fields governing the player's core state, push everything else into the fact graph, and enforce mutual exclusion in the reducer.

### Acceptance Criteria
- [x] Replace boolean/freeform character state flags with structured enums:
  - `stance`: Enum (`observing`, `hiding`, `negotiating`, `fleeing`, `fighting`)
  - `focus`: Single current objective/target
  - `tactics`: Short bounded list of active tactics with TTLs (e.g. "decoy_active: 2 turns")
  - `injury_state`: Bounded enum (e.g. `healthy`, `injured`, `critical`)
- [x] Implement strict mutual exclusion checks in `reduce_event` (e.g. cannot be `hiding` and `negotiating` unless in a specific multi-actor scene state).
- [x] Validate that unrecognized keys are shunted into a namespaced bag or the fact graph rather than floating as top-level variables.
- [x] Ensure 90%+ of unit/integration tests pass with updated schemas.

## Expected Files Changed
- `src/models/schemas.py`
- `src/services/rules/schema.py`
- `src/services/rules/reducer.py`
- `src/services/state_manager.py`

## Rollback Plan
- Revert the `models/schemas.py` and `services/rules/reducer.py` changes.
- Drop the new validation functions.

## Assumptions
- `state.unstructured` is an acceptable namespaced bag for non-canonical player-state keys.
- Structured-state enforcement is reducer-authoritative and does not require API contract changes.

## Validation Commands
- `python -m pytest tests/service/test_reducer.py -q`
- `python -m pytest tests/service/test_state_manager.py -q`
- `python -m pytest -q`
- `npm --prefix client run build`

## Implementation Notes
- Added canonical structured models (`stance`, `focus`, `tactics`, `injury_state`) in `src/models/schemas.py`.
- Added reducer schema constants/helpers for alias mapping, structured-value normalization, multi-actor checks, and unstructured-key detection.
- Updated reducer to:
  - map legacy flags to structured keys,
  - enforce mutual exclusion for conflicting stance updates per event (except multi-actor scene mode),
  - shunt non-canonical state-hint keys into `state.unstructured`,
  - reject increment ops against structured keys.
- Updated `AdvancedStateManager` to:
  - always maintain structured-state defaults,
  - maintain `state.unstructured`,
  - decay tactic TTLs on tick side-effects.
- Added focused tests for structured-state mapping, exclusion, shunting, injury validation, and tactic TTL decay.

## Evidence
- Full backend suite: `524 passed` (`python -m pytest -q`).
- Frontend build gate: `vite build` completed successfully (`npm --prefix client run build`).
