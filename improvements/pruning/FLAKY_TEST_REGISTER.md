# Flaky Test Register (Wave 0)

Date: `2026-03-06`  
Mode: additive evidence capture (no behavioral/code changes)

## Scope
- Capture currently known flaky candidates.
- Record reproducibility sampling notes.
- Keep a bounded watchlist for future stabilization work.

## Candidate Register
| Test | Why On Watchlist | Reproduction Sample (2026-03-06) | Status |
| --- | --- | --- | --- |
| `tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions` | Previously observed intermittent behavior in prior sessions; touches cutoff timestamps + shared cache cleanup | `10/10` passes (`0` failures) | `watchlist_open_not_reproduced` |
| `tests/api/test_game_cache_cleanup.py::TestCacheCleanupLogic::test_cleanup_endpoint_integration` | Exercises same cleanup endpoint with cache + DB interaction | `10/10` passes (`0` failures) | `watchlist_open_not_reproduced` |

## Reproduction Commands
```powershell
1..10 | ForEach-Object { pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions -q }
1..10 | ForEach-Object { pytest tests/api/test_game_cache_cleanup.py::TestCacheCleanupLogic::test_cleanup_endpoint_integration -q }
```

## Observed Stability Signals
- No failures in the two cleanup-related samples above.
- Repeated warnings remain present:
- Pydantic `model_id` protected namespace warnings.
- SQLite datetime adapter deprecation warnings in cleanup-related tests.

## Notes
- A prior test-node selector typo (`not found`) was command-selection error, not a runtime flake.
- Keep this register active until cleanup tests are consistently stable across broader suite runs and environments.
