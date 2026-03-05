# PR Evidence

## Change Summary

- Item ID(s): `59-introduce-authoritative-event-reducer-and-rulebook`, `69-implement-clean-3-layer-llm-architecture`
- PR Scope: Completed reducer-authority and strict staged-action architecture hardening together. `/api/next` inbound var mutations now flow through reducer policy instead of direct state writes. Action turns now persist a canonical Scene Card "Now", run planner/commit/narrator with reducer-committed deltas as the only authoritative state output, and persist reducer/system-tick receipts into action event metadata for replay/debug.
- Risk Level: `medium`

## Behavior Impact

- User-visible changes:
  - Action responses now expose reducer-committed `state_changes` only (authoritative commit output).
  - Stage-B narrator mutation attempts are explicitly ignored and flagged in reasoning warnings.
- Non-user-visible changes:
  - `/api/next` client var sync is now reducer-routed (`ChoiceSelectedIntent`) instead of direct `set_variable` writes.
  - Scene Card "Now" is persisted per turn in session state (`_scene_card_now`, bounded `_scene_card_history`).
  - Action events now include reducer receipts + scene card context in internal metadata for deterministic replay/debug.
  - Reducer now mirrors environment alias updates onto canonical environment object fields and records bounded unstructured-state pruning evidence.
- Explicit non-goals:
  - No API route/path additions.
  - No response schema contract breakage.
  - No migration introducing new DB tables.

## Validation Results

- `python -m pytest -q` -> `pass` (`534 passed, 14 warnings`)
- `python scripts/dev.py gate3` -> `pass` (ruff+black canonical scope, client build, compileall all green)
- `npm --prefix client run build` -> `pass` (`vite build completed successfully`)

## Contract and Compatibility

- Contract/API changes: `none` (existing routes and envelope shapes preserved)
- Migration/state changes: Session state now persists `_scene_card_now` and bounded `_scene_card_history` internal keys.
- Backward compatibility: Existing clients continue to work; strict 3-layer enforcement has explicit rollback flag (`WW_ENABLE_STRICT_THREE_LAYER_ARCHITECTURE`).

## Metrics (if applicable)

- Baseline:
  - N/A (architecture hardening slice)
- After:
  - N/A (validated via contract/integration tests and quality gates)

## Risks

- Persisted scene-card internals can grow if history bounds are loosened without review.
- Strict reducer routing may surface legacy client assumptions around blocked/internal keys.

## Rollback Plan

- Fast disable path: set `WW_ENABLE_STRICT_THREE_LAYER_ARCHITECTURE=false` to disable strict staged enforcement fallback behavior.
- Full revert path: revert this PR commit set (turn orchestration, reducer, scene-card persistence, and associated tests/docs).

## Follow-up Work

- `62-harden-world-memory-and-projection-spine-v2.md`
- `80-add-structured-logging-and-request-correlation-ids.md`
- `84-extend-narrative-eval-harness-with-coherence-metrics.md`
- `95-implement-two-phase-llm-parameter-sweep-harness.md`
