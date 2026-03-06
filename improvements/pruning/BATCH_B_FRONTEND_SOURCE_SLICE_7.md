# Batch B Frontend Source Slice 7

Date: `2026-03-06`
Status: `completed_with_transient_flake_note`

## Scope
- Extract the largest remaining orchestration block from `App.tsx` into a dedicated hook.
- Add explicit v3 narrator extension stubs (world/scene/player lanes) at the new architecture boundary.

## Changes
1. Added `client/src/hooks/useTurnOrchestration.ts`:
- moved `handleChoice(...)`, `handleAction(...)`, `handleMove(...)`, `fetchScene(...)`, and `refreshPostTurnContext(...)` out of `App.tsx`.
- retained current runtime behavior while consolidating the highest-complexity turn flow logic.

2. Added `client/src/app/v3NarratorStubs.ts`:
- introduced `V3NarratorHooks` with world/scene/player lane context/result shapes.
- provided no-op default `v3NarratorHooksStub` used as current runtime adapter seam.

3. Refactored `client/src/App.tsx`:
- replaced in-file turn orchestration logic with `useTurnOrchestration(...)` wiring.
- passed no-op narrator hooks to anchor v3 lane integration without behavior change.

4. Added v3 alignment notes:
- `improvements/VISION.md`
- `improvements/ROADMAP.md`

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`
- `pytest -q tests/service/test_storylet_selector.py::test_sparse_context_triggers_runtime_synthesis -q`
- `python scripts/dev.py quality-strict` (rerun)

Results:
- frontend build: pass
- strict gate: transient fail once at `tests/service/test_storylet_selector.py::test_sparse_context_triggers_runtime_synthesis`
- isolated rerun of failing node: pass
- strict gate rerun: pass (`590 passed`)

## Batch B Impact
- Removed the largest remaining action/choice/move orchestration complexity from `App.tsx`.
- Established explicit narrator-lane stubs at the frontend turn orchestration seam for v3 planning.
