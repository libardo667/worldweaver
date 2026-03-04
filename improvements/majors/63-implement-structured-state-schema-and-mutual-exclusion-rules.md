# Major 63: Implement structured state schema and mutual exclusion rules

## Problem Statement
The game state currently relies on dozens of ad-hoc boolean flags, unstructured strings, and numeric trackers that can grow without bounds or conceptually conflict (e.g. a player being simultaneously `hiding` and `negotiating`). This "leaky, redundant" state causes the LLM to lose focus on the core narrative physics, creating a dreamlike, inconsistent experience. The authoritative reducer (Major 59) laid the groundwork; we now need a formal schema to enforce world rules.

## Proposed Solution
Replace the sprawling freeform variables with 3-5 structured fields governing the player's core state, push everything else into the fact graph, and enforce mutual exclusion in the reducer.

### Acceptance Criteria
- [ ] Replace boolean/freeform character state flags with structured enums:
  - `stance`: Enum (`observing`, `hiding`, `negotiating`, `fleeing`, `fighting`)
  - `focus`: Single current objective/target
  - `tactics`: Short bounded list of active tactics with TTLs (e.g. "decoy_active: 2 turns")
  - `injury_state`: Bounded enum (e.g. `healthy`, `injured`, `critical`)
- [ ] Implement strict mutual exclusion checks in `reduce_event` (e.g. cannot be `hiding` and `negotiating` unless in a specific multi-actor scene state).
- [ ] Validate that unrecognized keys are shunted into a namespaced bag or the fact graph rather than floating as top-level variables.
- [ ] Ensure 90%+ of unit/integration tests pass with updated schemas.

## Expected Files Changed
- `src/models/schemas.py`
- `src/services/rules/schema.py`
- `src/services/rules/reducer.py`
- `src/services/state_manager.py`

## Rollback Plan
- Revert the `models/schemas.py` and `services/rules/reducer.py` changes.
- Drop the new validation functions.
