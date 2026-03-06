# Flaky Test Register (Wave 0)

Date: `2026-03-06`  
Mode: stabilization follow-up evidence

## Scope
- Capture currently known flaky candidates.
- Record reproducibility sampling notes.
- Keep a bounded watchlist for future stabilization work.

## Candidate Register
| Test | Why On Watchlist | Reproduction Sample (2026-03-06) | Status |
| --- | --- | --- | --- |
| `tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions` | Previously observed intermittent behavior tied to timestamp/setup path in cleanup flow | Pre-fix: strict-run sample `0/3` passes (`3` failures). Post-fix: isolated sample `10/10` passes (`0` failures) + `quality-strict` pass (`590 passed`) | `stabilized_burn_in_started` |
| `tests/api/test_game_cache_cleanup.py::TestCacheCleanupLogic::test_cleanup_endpoint_integration` | Exercises same cleanup endpoint with cache + DB interaction | `10/10` passes (`0` failures) | `watchlist_open_not_reproduced` |

## Reproduction Commands
```powershell
1..10 | ForEach-Object { pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions -q }
1..10 | ForEach-Object { pytest tests/api/test_game_cache_cleanup.py::TestCacheCleanupLogic::test_cleanup_endpoint_integration -q }
python scripts/dev.py quality-strict
```

## Observed Stability Signals
- Cleanup stale-session node was stabilized by deterministic direct DB setup in test fixture flow.
- Post-fix evidence currently shows no isolated-repeat failures and one full strict-suite pass.
- No isolated-repeat failures observed yet for cleanup endpoint integration node.
- Repeated warnings remain present:
- Pydantic `model_id` protected namespace warnings.
- SQLite datetime adapter deprecation warnings in cleanup-related tests.

## Notes
- A prior test-node selector typo (`not found`) was command-selection error, not a runtime flake.
- Keep this register active until cleanup tests clear additional full-suite burn-in cycles.
