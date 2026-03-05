# PR Evidence: Minor 88 - Backfill Primary Goal When Empty After Initial Turn

## Item

`improvements/minors/archive/88-backfill-primary-goal-when-empty-after-initial-turn.md`

## Scope

Added deterministic, idempotent primary-goal backfill behavior after the initial turn so sessions do not drift forward without an explicit goal thesis.

## What Changed

| File | Change |
|------|--------|
| `src/services/state_manager.py` | Added deterministic fallback thesis derivation and `backfill_primary_goal_if_empty_after_initial_turn(...)`, including source/note metadata (`system_goal_backfill`, `auto_backfill_after_initial_turn`) and strict no-op conditions (goal already present, below turn threshold). |
| `src/services/turn_service.py` | Wired goal-backfill invocation into the `/next` turn orchestration path after committed state updates; added timing metric and structured `goal_backfilled` event emission. |
| `tests/service/test_state_manager.py` | Added deterministic/idempotent unit tests for goal backfill and pre-turn no-op behavior. |
| `tests/service/test_semantic_selector.py` | Added coverage proving semantic context input includes `Goal:` content after backfill assignment. |
| `tests/api/test_game_endpoints.py` | Added endpoint tests for backfill timing/idempotency and explicit-goal non-overwrite behavior. |
| `improvements/ROADMAP.md` | Marked minor `88` complete and removed it from pending execution order. |
| `improvements/minors/archive/88-backfill-primary-goal-when-empty-after-initial-turn.md` | Item doc finalized with scope/assumptions/validation/rollback and acceptance marked complete. |

## Why This Matters

- Prevents early-turn narrative drift caused by empty `primary_goal` state.
- Improves semantic selection quality because goal context is consistently present in embedding/scoring input.
- Increases arc coherence with deterministic behavior that is replayable and testable, not prompt-luck dependent.

## Acceptance Criteria Check

- [x] Sessions do not continue past initial gameplay turns with empty `primary_goal`.
- [x] Fallback goal generation is deterministic and idempotent per session.
- [x] Goal context appears in semantic scoring inputs after fallback assignment.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No API route/path/payload contract changes were introduced.

### Gate 2: Correctness

- `python -m pytest tests/service/test_state_manager.py -q` -> pass (29 passed)
- `python -m pytest tests/service/test_semantic_selector.py -q` -> pass (21 passed)
- `python -m pytest tests/api/test_game_endpoints.py -q` -> pass (47 passed)
- `python -m pytest -q` -> pass (`544 passed, 14 warnings`)

### Gate 3: Build and Static Health

- `python scripts/dev.py lint-all` -> pass
- `npm --prefix client run build` -> pass

## Operational Safety / Rollback

- Rollback path: revert this PR's state-manager backfill logic, turn-orchestration call site, and associated tests.
- Safe-disable path: remove/guard the single `backfill_primary_goal_if_empty_after_initial_turn(...)` invocation in `TurnOrchestrator`.
- No DB migrations, schema migrations, or irreversible data transforms were introduced.

## Residual Risk

- Fallback thesis quality is intentionally simple and deterministic; it favors stability over stylistic richness.
- Sessions with sparse role/world context may receive generic fallback language, which is acceptable for this guardrail-focused minor.
