# Minor 98: Fix prefetch status contract mismatch in long-run harness

## Metadata

- ID: 98-fix-prefetch-status-contract-in-long-run-harness
- Type: minor
- Owner: levi
- Status: done
- Risk: low

## Problem

`playtest_harness/long_run_harness.py` currently treats prefetch as complete only when `status["prefetch_complete"]` is truthy. The actual `/api/prefetch/status/{session_id}` response contract (validated in `tests/api/test_prefetch_endpoints.py`) is `{"stubs_cached": int, "expires_in_seconds": int}`. This mismatch causes `_await_prefetch()` to spin until timeout in many turns, creating large hidden wait overhead in sweeps.

## Proposed Solution

Update `_await_prefetch()` to align with the current status payload while preserving backward compatibility:

- If `prefetch_complete` exists, honor it.
- Otherwise, treat prefetch as complete when `stubs_cached > 0` or `expires_in_seconds > 0`.
- Keep polling best-effort and tolerant of transient request failures.
- Reduce default wait timeout from the current long fallback to a bounded value appropriate for sweep loops.

## Files Affected

- `playtest_harness/long_run_harness.py`
- `tests/integration/test_turn_progression_simulation.py`
- `tests/integration/test_parameter_sweep_harness.py`

## Acceptance Criteria

- [x] `_await_prefetch()` exits quickly when status payload reports `stubs_cached` and/or `expires_in_seconds` without requiring a nonexistent `prefetch_complete` key.
- [x] Legacy compatibility remains: if `prefetch_complete` is present and true, wait exits successfully.
- [x] A targeted regression test fails on the old logic and passes with the new logic.
- [x] Harness regression tests now explicitly guard against per-turn timeout inflation attributable to `_await_prefetch()` polling mismatch.

## Validation Commands

- `python -m pytest tests/api/test_prefetch_endpoints.py -q`
- `python -m pytest tests/integration/test_turn_progression_simulation.py -q`
- `python -m pytest tests/integration/test_parameter_sweep_harness.py -q`

## Risks and Rollback

- Risk: A too-permissive completion rule could exit before meaningful prefetch population in edge cases.
- Rollback: Revert this item commit and temporarily restore previous waiting behavior while adding stronger completion signaling.
