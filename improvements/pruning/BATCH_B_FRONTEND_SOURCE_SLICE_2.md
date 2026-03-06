# Batch B Frontend Source Slice 2

Date: `2026-03-06`
Status: `completed_with_flaky_gate_note`

## Scope
- Continue `frontend_source` simplification by moving large presentation blocks out of `App.tsx`.
- Preserve behavior while reducing top-level component JSX complexity.

## Changes
1. Added `client/src/components/AppTopbar.tsx`:
- extracted mode tabs, session/meta status, settings trigger, and reset controls from `App.tsx`.
- preserved existing classes/props behavior and constellation/dev-reset gating.

2. Refactored `client/src/App.tsx`:
- replaced inline topbar JSX with `<AppTopbar ... />` wiring.
- retained all prior event handlers/state sources; changed only presentation composition boundary.

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`
- `pytest -q tests/api/test_game_endpoints.py::TestGameEndpoints::test_next_applies_pending_choice_commit_storylet_effects_once -q`
- `pytest -q tests/api/test_action_endpoint.py::TestActionEndpoint::test_action_event_metadata_includes_reducer_receipts -q`

Results:
- frontend build: pass
- strict gate: blocked by preexisting flaky API test nodes in full-suite context (non-frontend paths)
  - `tests/api/test_game_endpoints.py::TestGameEndpoints::test_next_applies_pending_choice_commit_storylet_effects_once`
  - `tests/api/test_action_endpoint.py::TestActionEndpoint::test_action_event_metadata_includes_reducer_receipts`
- isolated reruns of both failing nodes: pass

## Batch B Impact
- `App.tsx` shrank from `1051` lines to `976` lines in this slice.
- UI shell/header concerns are now isolated for faster future App simplification slices.
