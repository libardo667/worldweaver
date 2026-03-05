# Add deterministic world simulation systems that tick per turn and emit composable deltas

## Problem

World state currently evolves mostly from explicit player/story events. There is
no standardized deterministic "systems tick" layer where independent simulation
subsystems push on shared state each turn.

This limits emergent cross-system behavior and makes world evolution overly
reactive to direct player writes.

## Proposed Solution

Introduce a deterministic simulation tick framework:

1. Add `world_simulation.tick(...)` that runs once per committed turn and emits
   system deltas without direct side effects.
2. Implement initial pluggable systems (deterministic, data-driven), for example:
   - environmental pressure/tide progression,
   - location degradation/drift,
   - maintenance/recovery effects.
3. Feed system deltas through the same reducer/rulebook used by player events.
4. Record simulation tick events via `world_memory.record_event` with explicit
   provenance metadata.
5. Allow mode/config control for tick policy (turn-based baseline; optional
   future real-time mode).

## Files Affected

- `src/services/world_memory.py`
- `src/services/state_manager.py`
- `src/services/simulation/tick.py` (new)
- `src/services/simulation/systems.py` (new)
- `src/api/game/story.py`
- `src/api/game/action.py`
- `src/config.py`
- `tests/service/test_world_simulation.py` (new)
- `tests/integration/test_turn_progression_simulation.py` (new)

## Acceptance Criteria

- [ ] A deterministic tick runs once per committed turn and produces repeatable
      deltas for the same starting state and inputs.
- [ ] Tick deltas are applied through the authoritative reducer, not by direct
      state mutation.
- [ ] Tick-generated events are persisted with source metadata and visible in
      world history/projection.
- [ ] Tick can be disabled/tuned via configuration.
- [ ] New simulation tests pass and do not break existing route contracts.

## Risks & Rollback

Risk: poorly tuned system rates can create runaway world-state drift and degrade
narrative pacing.

Rollback:

1. Ship with conservative defaults and a global kill switch.
2. Keep system modules isolated so individual subsystems can be disabled
   independently.
3. Disable tick integration entirely if pacing regressions are detected, while
   retaining event logs for diagnostics.

