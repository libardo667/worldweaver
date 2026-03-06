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
| `tests/api/test_game_endpoints.py::TestGameEndpoints::test_next_applies_pending_choice_commit_storylet_effects_once` | Failed in strict full-suite context while frontend-only simplify slice was running; warning indicates world-event persistence refresh issue | Full-suite sample: `0/1` pass (`1` failure), later strict run pass observed. Isolated rerun: `1/1` pass | `watchlist_transient_full_suite` |
| `tests/api/test_action_endpoint.py::TestActionEndpoint::test_action_event_metadata_includes_reducer_receipts` | Failed in strict full-suite context with world-event persistence warning | Full-suite sample: `0/1` pass (`1` failure), later strict run pass observed. Isolated rerun: `1/1` pass | `watchlist_transient_full_suite` |
| `tests/service/test_storylet_selector.py::test_sparse_context_triggers_runtime_synthesis` | Failed once in strict full-suite context during frontend slice 7 with no touched backend service files | Full-suite sample: `0/1` pass (`1` failure), isolated rerun: `1/1` pass, subsequent strict rerun pass observed | `watchlist_transient_full_suite` |
| `tests/api/test_game_endpoints.py::TestGameEndpoints::test_session_bootstrap_purges_prior_same_session_state_and_prefetch` | Failed once in strict full-suite context during frontend slice 14 with no touched backend API/service files | Full-suite sample: `0/1` pass (`1` failure), isolated reruns: `4/4` passes, subsequent strict rerun pass observed | `watchlist_transient_full_suite` |

## Reproduction Commands
```powershell
1..10 | ForEach-Object { pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions -q }
1..10 | ForEach-Object { pytest tests/api/test_game_cache_cleanup.py::TestCacheCleanupLogic::test_cleanup_endpoint_integration -q }
pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_next_applies_pending_choice_commit_storylet_effects_once -q
pytest tests/api/test_action_endpoint.py::TestActionEndpoint::test_action_event_metadata_includes_reducer_receipts -q
pytest tests/service/test_storylet_selector.py::test_sparse_context_triggers_runtime_synthesis -q
1..3 | ForEach-Object { pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_session_bootstrap_purges_prior_same_session_state_and_prefetch -q }
pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_session_bootstrap_purges_prior_same_session_state_and_prefetch -q
python scripts/dev.py quality-strict
```

## Observed Stability Signals
- Cleanup stale-session node was stabilized by deterministic direct DB setup in test fixture flow.
- Post-fix evidence currently shows no isolated-repeat failures and one full strict-suite pass.
- No isolated-repeat failures observed yet for cleanup endpoint integration node.
- Additional intermittent failures appeared in full strict context for two world-event metadata nodes; each passed immediately in isolated reruns.
- A later full strict-suite pass did not reproduce those two metadata-node failures, but they remain on watchlist pending more burn-in.
- One transient service-level sparse-context synthesis failure was observed and then not reproduced in isolated/full reruns.
- One transient bootstrap/prefetch cleanup node failure was observed in full strict context, then passed in repeated isolated reruns and subsequent strict rerun.
- Repeated warnings remain present:
- Pydantic `model_id` protected namespace warnings.
- SQLite datetime adapter deprecation warnings in cleanup-related tests.
- SAWarning/refresh warnings around world-event persistence during failing full-suite runs.

## Notes
- A prior test-node selector typo (`not found`) was command-selection error, not a runtime flake.
- Keep this register active until cleanup tests clear additional full-suite burn-in cycles.
