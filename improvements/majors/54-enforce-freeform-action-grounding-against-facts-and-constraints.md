# Enforce freeform action grounding against projected facts, affordances, and mutation constraints

## Problem

`src/services/command_interpreter.py` has staged interpretation and sanitization,
but mutation permissiveness is still largely model-proposed and text-mediated.
The current path can still accept broad state deltas when explicit affordance
constraints are not centralized.

This weakens coherence when models are more creative and allows implicit
"self-granted permissions" in edge cases.

## Proposed Solution

Add a strict action resolution contract with three explicit phases:

1. **Intent**: parse action intent and proposed effects (existing staged path).
2. **Validate**: evaluate proposed effects against:
   - projected world facts,
   - inventory and location affordances,
   - allowed mutation schema/rules.
3. **Commit**: apply only validated deltas, emit rejection/partial-acceptance
   reasons for blocked effects, then narrate from committed state.

Implementation details:

- Extract validation logic into a dedicated policy module.
- Add machine-readable rejection reasons to action metadata.
- Keep route contracts stable while extending metadata fields for debug insight.

## Files Affected

- `src/services/command_interpreter.py`
- `src/services/world_memory.py`
- `src/services/state_manager.py`
- `src/api/game/action.py`
- `src/models/schemas.py`
- `tests/service/test_command_interpreter.py`
- `tests/api/test_action_endpoint.py`

## Acceptance Criteria

- [ ] Freeform actions that conflict with projected facts or location/inventory
      affordances are rejected or partially applied with explicit reasons.
- [ ] Only whitelisted mutation paths are commit-eligible.
- [ ] Narration reflects committed state, not raw proposed state.
- [ ] Action metadata exposes validation outcomes for debugging.
- [ ] Existing action endpoint payload shape remains backward compatible.
- [ ] `python -m pytest -q tests/service/test_command_interpreter.py
      tests/api/test_action_endpoint.py` passes.

## Risks & Rollback

Risk: overly strict validation can reduce player freedom and make responses feel
mechanical.

Rollback:

1. Gate strict validation with a feature flag and keep current sanitization as
   fallback.
2. Tune blocked/allowed rule sets using test fixtures before broad enablement.
3. Revert policy module integration and retain existing staged flow if severe
   regressions occur.

