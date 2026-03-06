# Baseline Freeze Evidence (Stage 3)

Date: `2026-03-06`  
Mode: additive-only assessment artifacts (no pruning edits)

## Commands Executed
1. `python scripts/dev.py quality-strict`
2. `pytest tests/api/test_action_endpoint.py tests/api/test_prefetch_endpoints.py tests/service/test_storylet_selector.py -q`
3. `pytest tests/api/test_settings_readiness.py tests/service/test_prefetch_service.py -q`
4. `pytest tests/api/test_game_endpoints.py -q`
5. `pytest tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions -q` (5 runs)

## Results
1. `quality-strict`: failed on formatting gate only.
2. Action/prefetch/selector pack: `41 passed`, `3 warnings`.
3. Readiness/prefetch-service pack: `12 passed`, `3 warnings`.
4. Game endpoints pack: `51 passed`, `10 warnings`.
5. Cleanup stale-session test (repeat): `0/5 failures` in this sampling.

## Baseline Risks Noted
- Formatting gate is currently red in strict mode due files that would be reformatted.
- `test_cleanup_removes_stale_sessions` has shown intermittent behavior in previous runs/sessions; it did not reproduce in this sample.
- Repeated warnings from Pydantic protected namespace on `model_id` fields.
- SQLite datetime adapter deprecation warnings appear in cleanup-related tests.

## Interpretation
- Core API behavior baseline currently passes in sampled suites.
- Strict quality is not green due style gate, so baseline must be treated as "functionally passing, formatting-blocked."
- Flake remains a tracked risk until stabilized with deterministic test setup/assertions.
