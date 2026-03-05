# Major 97: Harden sweep latency accounting and prefetch wait policy

## Metadata

- ID: 97-harden-sweep-latency-accounting-and-prefetch-policy
- Type: major
- Owner: levi
- Status: done
- Risk: medium
- Target Window: 2026-03
- Depends On: 98-fix-prefetch-status-contract-in-long-run-harness

## Problem

`scripts/dev.py sweep` currently feels much slower than reported per-request latency because harness wall-clock overhead is not modeled clearly and prefetch completion checks are brittle.

Concrete evidence:

- In `playtest_harness/long_run_harness.py`, `_await_prefetch()` polls `/prefetch/status/{session_id}` and only exits when `prefetch_complete` is truthy.
- `src/api/game/prefetch.py` and `tests/api/test_prefetch_endpoints.py` define a stable response shape of `{"stubs_cached": int, "expires_in_seconds": int}` with no `prefetch_complete` key.
- Result: post-turn loops frequently run until timeout, inflating `summary.elapsed_ms` while `summary.latency_ms_avg` still reflects request time only.
- `playtest_harness/parameter_sweep.py` ranks configs by request latency/repetition/failure but does not expose prefetch wait overhead as a first-class metric, which obscures diagnosis when sweeps "feel" glacial.

## Proposed Solution

Implement a sweep/runtime latency model that separates request time from harness overhead and makes prefetch wait behavior explicit.

Scope:

1. Build a robust prefetch completion predicate in `long_run_harness` that supports the stable status payload (`stubs_cached`, `expires_in_seconds`) and optional legacy `prefetch_complete`.
2. Add explicit prefetch-wait policy knobs to run config and CLI flow (for example: `off`, `bounded`, `strict`) with bounded defaults for sweeps.
3. Track and persist separate timing metrics in run summaries:
   - request latency metrics (current behavior),
   - prefetch wait totals/percentiles,
   - end-to-end turn and run wall-clock metrics.
4. Propagate these metrics through `parameter_sweep.py` so phase summaries expose both ranking metrics and overhead diagnostics.
5. Extend integration coverage for phase summaries and latency field shape stability.

## Files Affected

- `playtest_harness/long_run_harness.py`
- `playtest_harness/parameter_sweep.py`
- `tests/integration/test_parameter_sweep_harness.py`
- `tests/integration/test_turn_progression_simulation.py`
- `scripts/dev.py`

## Non-Goals

- No API contract changes for `/api/prefetch/status/{session_id}`.
- No redesign of LLM pipeline or model provider configuration.
- No removal of spawn-per-config sweep mode.

## Acceptance Criteria

- [x] Harness prefetch completion logic supports both stable status payload fields and legacy `prefetch_complete` without forcing timeout waits on healthy runs.
- [x] Run summary payload includes explicit prefetch wait metrics separate from request latency metrics.
- [x] Sweep phase summaries preserve current ranking behavior while adding visibility into overhead contributors (prefetch wait and backend mode/startup overhead).
- [x] CLI/docs provide clear controls for prefetch wait policy during sweeps and long runs.
- [x] Integration tests assert new summary fields and guard against regression to hidden post-turn timeout inflation.

## Validation Commands

- `python -m pytest tests/api/test_prefetch_endpoints.py -q`
- `python -m pytest tests/integration/test_parameter_sweep_harness.py -q`
- `python -m pytest tests/integration/test_turn_progression_simulation.py -q`
- `python scripts/dev.py quality-strict`

## Risks and Rollback

Risks:

- Changing summary schema can break downstream scripts that parse sweep artifacts.
- Reducing/altering waits can hide prefetch degradation if diagnostics are not captured.

Rollback:

- Revert the harness/sweep commits for this item.
- Temporarily force strict waiting behavior and old metric output behind default settings until downstream consumers are updated.

## Follow-up Candidates

- Add a dedicated sweep artifact diff utility that compares request latency vs overhead latency trends across runs.
- Add a backend-side prefetch completion signal field once contract changes are explicitly approved.
