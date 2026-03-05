# PR Evidence: Minor 98 - Fix Prefetch Status Contract Mismatch in Long-Run Harness

## Item

`improvements/minors/98-fix-prefetch-status-contract-in-long-run-harness.md`

## Scope

Aligned harness-side prefetch completion detection with the stable API contract exposed by `/api/prefetch/status/{session_id}` and added regression coverage to prevent timeout-driven latency inflation in sweep loops.

## What Changed

| File | Change |
|------|--------|
| `playtest_harness/long_run_harness.py` | Added `_prefetch_status_complete(...)` compatibility predicate; updated `_await_prefetch(...)` to use stable fields (`stubs_cached`, `expires_in_seconds`) with legacy `prefetch_complete` support; reduced default wait timeout from `15.0` to bounded `3.0` seconds via `DEFAULT_PREFETCH_WAIT_TIMEOUT_SECONDS`. |
| `tests/integration/test_parameter_sweep_harness.py` | Added direct contract/compatibility tests for `_prefetch_status_complete(...)` using stable and legacy payload shapes. |
| `tests/integration/test_turn_progression_simulation.py` | Added `_await_prefetch(...)` regression tests proving immediate exit on stable status payloads and backward-compatible behavior for legacy `prefetch_complete`. |
| `improvements/minors/98-fix-prefetch-status-contract-in-long-run-harness.md` | Marked status `done` and checked acceptance criteria with test-backed wording. |
| `improvements/ROADMAP.md` | Marked minor `98` complete and removed it from active minor queue. |

## Why This Matters

- Sweep runtime was being dominated by harness-side waiting, not just model/API latency, because `_await_prefetch(...)` polled for a field the API never returns.
- That mismatch made comparative latency data less trustworthy by inflating wall-clock time independently of `/next` and `/action` request durations.
- This fix restores contract fidelity between harness and API, so sweep elapsed time better reflects real backend behavior.
- The new regression tests specifically guard the failure mode that caused repeated timeout waits, preventing silent reintroduction.

## Acceptance Criteria Check

- [x] `_await_prefetch()` exits quickly when status payload reports `stubs_cached` and/or `expires_in_seconds`.
- [x] Legacy compatibility remains when `prefetch_complete` is present.
- [x] Targeted regression tests cover old failure mode and new completion logic.
- [x] Harness tests explicitly guard against timeout-inflation behavior caused by status-field mismatch.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No API route/path/payload changes.
- Harness updated to match existing API contract (`stubs_cached`, `expires_in_seconds`).

### Gate 2: Correctness

- `python -m pytest tests/api/test_prefetch_endpoints.py -q` -> pass (`4 passed`)
- `python -m pytest tests/integration/test_turn_progression_simulation.py -q` -> pass (`4 passed`)
- `python -m pytest tests/integration/test_parameter_sweep_harness.py -q` -> pass (`6 passed`)

### Gate 3: Build and Static Health

- Not run in this item; scoped to required item validation commands above.

## Operational Safety / Rollback

- Fast disable path: set `WW_PREFETCH_WAIT_TIMEOUT_SECONDS=15` to restore previous wait ceiling if needed during investigation.
- Full revert path: revert changes in `playtest_harness/long_run_harness.py` and associated regression tests.
- Data/migration impact: none.

## Residual Risk

- The completion heuristic treats positive TTL as completion signal in the stable contract. If backend semantics change, this predicate must be updated in lockstep with API tests.
