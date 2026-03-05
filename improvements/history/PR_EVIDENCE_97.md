# PR Evidence: Major 97 - Harden Sweep Latency Accounting and Prefetch Wait Policy

## Item

`improvements/majors/97-harden-sweep-latency-accounting-and-prefetch-policy.md`

## Scope

Implemented explicit prefetch wait policy controls, separated request latency from harness overhead metrics, and propagated overhead diagnostics through sweep artifacts while preserving existing ranking semantics.

## What Changed

| File | Change |
|------|--------|
| `playtest_harness/long_run_harness.py` | Added `prefetch_wait_policy` and `prefetch_wait_timeout_seconds` to `RunConfig`; added CLI flags `--prefetch-wait-policy` and `--prefetch-wait-timeout-seconds`; added policy timeout resolver; updated `_await_prefetch` to return elapsed wait time; recorded per-turn `prefetch_wait_duration_ms` and `turn_duration_ms`; expanded run summary with request-vs-prefetch-vs-turn-wallclock metrics plus harness overhead totals; preserved legacy `latency_ms_*` fields. |
| `playtest_harness/parameter_sweep.py` | Passed prefetch policy/time into run configs; added per-run metrics for request latency, prefetch wait, wallclock, harness overhead, and backend startup mode/time; exposed policy/time in phase summaries and manifest; added phase-level `overhead_diagnostics`; kept ranking/scoring keyed on existing latency/failure/repetition fields. |
| `tests/integration/test_parameter_sweep_harness.py` | Added coverage for prefetch timeout policy defaults and aggregate overhead metric shape/stability; updated dry-run phase A expectations for new policy/diagnostic fields. |
| `tests/integration/test_turn_progression_simulation.py` | Updated prefetch wait tests to assert elapsed timing return and backward-compatible behavior. |
| `README.md` | Added usage lines documenting new prefetch wait controls for sweep and long-run harness workflows. |
| `improvements/majors/97-harden-sweep-latency-accounting-and-prefetch-policy.md` | Marked item status done and checked acceptance criteria. |
| `improvements/ROADMAP.md` | Marked major `97` complete and removed active major queue entry. |
| `tests/api/test_minimal.py` | Removed one unused import to unblock strict lint gate execution (`quality-strict`). |

## Why This Matters

- Before this change, sweep wall-clock latency could be dominated by harness-side waiting while ranking mostly observed request latency, making root-cause analysis and tuning decisions unreliable.
- The harness now distinguishes:
  - request latency (API/model path),
  - prefetch wait latency (post-turn harness behavior),
  - end-to-end turn wall-clock and non-request overhead.
- Sweep artifacts now surface overhead diagnostics directly, including backend spawn startup contribution, so “slow run” investigations are actionable.
- Prefetch waiting is now an explicit policy decision (`off|bounded|strict`) instead of implicit behavior, which improves repeatability across optimization experiments.

## Acceptance Criteria Check

- [x] Prefetch completion logic supports stable status fields and legacy compatibility.
- [x] Run summary now includes explicit prefetch wait metrics separate from request latency.
- [x] Sweep phase summaries include overhead diagnostics and backend mode/startup visibility.
- [x] CLI/docs expose prefetch wait policy controls for both sweeps and long runs.
- [x] Integration tests cover summary/metric behavior and regression-prone prefetch wait logic.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No API route or payload contract changes.
- Harness-side parsing aligns with existing `/api/prefetch/status/{session_id}` contract.

### Gate 2: Correctness

- `python -m pytest tests/api/test_prefetch_endpoints.py -q` -> pass (`4 passed`, `3 warnings`)
- `python -m pytest tests/integration/test_parameter_sweep_harness.py -q` -> pass (`8 passed`)
- `python -m pytest tests/integration/test_turn_progression_simulation.py -q` -> pass (`4 passed`, `3 warnings`)

### Gate 3: Build and Static Health

- `python scripts/dev.py quality-strict` -> pass  
  - `ruff + black` pass  
  - client build pass  
  - compileall pass  
  - pytest warning budget pass (`561 passed, 14 warnings`, budget allowed `14`)

## Additional Verification

- `python scripts/dev.py sweep --phase a --dry-run --phase-a-configs 1 --prefetch-wait-policy off --prefetch-wait-timeout-seconds 0` -> pass
- Verified `phase_a_summary.json` includes:
  - `prefetch_wait_policy`
  - `prefetch_wait_timeout_seconds`
  - `overhead_diagnostics`

## Operational Safety / Rollback

- Fast disable path: run with `--prefetch-wait-policy off` (or set tight bounded timeout) to eliminate post-turn waiting overhead immediately during sweeps.
- Configuration rollback path: set `--prefetch-wait-policy strict --prefetch-wait-timeout-seconds 15` to emulate prior long-wait behavior.
- Full revert path: revert this major’s harness/sweep/test/doc commits.
- Data/migration impact: none (artifact schema expanded; no DB/state migration).

## Residual Risk

- Expanded summary/metric shape may require downstream consumer updates if they assume a fixed schema.
- Ranking still optimizes existing composite score; teams should periodically cross-check ranking outcomes against narrative-eval quality signals.
