# Unify session start with bootstrap-seeded first playable turn

## Problem
The current onboarding loop is split across two route calls:

1. `POST /session/bootstrap` seeds world/session scaffolding and storylets.
2. `POST /next` produces the first playable scene, choices, and most turn diagnostics.

This creates product and architecture friction:

- Clients must orchestrate a two-step startup before the user sees the first actionable turn.
- First-turn goal/arc readiness is inconsistent with v3 intent. Goal backfill is currently thresholded after arc turn count reaches one, which usually means the first playable scene can still start with an empty `primary_goal`.
- Harnesses (including sweeps) measure startup plus first-turn behavior indirectly, making startup-path regressions harder to isolate.

## Proposed Solution
Introduce a unified startup contract that returns a seeded first turn in one authoritative flow, while preserving existing routes for compatibility.

1. Add `POST /session/start` (or equivalent additive contract) that executes:
   - session bootstrap generation/persistence,
   - initial goal/arc/player-state seeding from bootstrap outputs,
   - first `next`-turn orchestration,
   - all under a single session mutation lock with rollback safety.
2. Return a single response payload containing:
   - bootstrap metadata (`storylets_created`, world seed info, bootstrap state),
   - first playable turn payload (`text`, `choices`, `vars`, diagnostics),
   - startup diagnostics needed by harness/replay tooling.
3. Keep `POST /session/bootstrap` and `POST /next` unchanged for backward compatibility.
4. Keep sweeps stable by default:
   - no required migration for current sweep workflows,
   - optional sweep flag/path can be added later to exercise unified startup explicitly.

## Files Affected
- `src/models/schemas.py`
- `src/api/game/state.py`
- `src/api/game/orchestration_adapters.py`
- `src/services/world_bootstrap_service.py`
- `src/services/turn_service.py`
- `playtest_harness/long_run_harness.py`
- `playtest_harness/parameter_sweep.py`
- `tests/api/test_game_endpoints.py`
- `tests/integration/test_turn_progression_simulation.py`

## Non-Goals
- Replacing or removing existing `/session/bootstrap` and `/next` routes.
- Changing reducer authority or projection canon rules.
- Forcing sweep harnesses to switch startup mode immediately.

## Acceptance Criteria
- [ ] A single startup request can return bootstrap outputs and first playable turn data together.
- [ ] First playable turn includes seeded goal/arc context and actionable choices.
- [ ] Existing `/session/bootstrap` + `/next` clients continue to work unchanged.
- [ ] Unified startup path is lock-safe and rollback-safe under failure.
- [ ] Harness support can opt into unified startup without breaking existing sweep baselines.

## Validation Commands
- `pytest -q tests/api/test_game_endpoints.py`
- `pytest -q tests/integration/test_turn_progression_simulation.py`
- `pytest -q tests/integration/test_parameter_sweep_phase_a.py tests/integration/test_parameter_sweep_ranking.py`
- `python scripts/dev.py quality-strict`

## Risks & Rollback
- Risk: startup contract complexity can blur ownership between bootstrap and turn orchestration.
- Risk: accidental route-contract coupling can break legacy clients if response fields are not additive.
- Risk: sweep comparability can drift if startup mode is mixed without explicit labeling.

Rollback:

- Feature-flag the unified startup path off and continue using existing `/session/bootstrap` + `/next`.
- Retain additive schema fields but stop emitting unified startup payloads until fixes land.
