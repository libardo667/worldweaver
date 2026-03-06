# Batch B Tests Integration Slice 6

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue large-slice simplification of `tests_integration` by separating API integration from harness utility coverage.
- Introduce parametrization/helper reuse for repeated integration assertions.
- Improve script/harness subprocess assertion consistency.

## Changes
1. Separated harness utility tests from API turn progression integration:
- `tests/integration/test_turn_progression_simulation.py`
  - now focuses on API simulation-tick integration behavior.
- `tests/integration/test_long_run_harness_helpers.py` (new)
  - moved `_await_prefetch(...)` and motif-reuse helper tests here.

2. Expanded shared helper reuse:
- `tests/integration_harness_helpers.py`
  - added `run_subprocess_capture(...)`
  - added `assert_subprocess_success(...)`
  - added `assert_nested_values(...)`
  - expanded `build_turn_record(...)` for flexible phase/action-source setup.
- `tests/integration_helpers.py`
  - added `assert_status_in(...)`.

3. Simplified/parametrized integration tests:
- `tests/integration/test_narrative_eval_harness.py`
  - now uses shared subprocess helpers.
- `tests/integration/test_spatial_navigation_integration.py`
  - direction checks converted to parametrized test cases.
- `tests/integration/test_benchmark_three_layer.py`
  - assertion bundles moved to shared helper-based comparisons.

## Guardrail Verification
Commands:
- `ruff check tests/integration_helpers.py tests/integration_harness_helpers.py tests/integration/test_turn_progression_simulation.py tests/integration/test_long_run_harness_helpers.py tests/integration/test_narrative_eval_harness.py tests/integration/test_spatial_navigation_integration.py tests/integration/test_benchmark_three_layer.py`
- `pytest -q tests/integration`
- `python scripts/dev.py quality-strict`

Results:
- Lint: pass
- Integration suite: `52 passed`
- Full strict gate: pass (`590 passed`)
- Flaky follow-up stabilization:
  - target node: `tests/api/test_game_endpoints.py::TestGameEndpoints::test_cleanup_removes_stale_sessions`
  - stabilization change: direct DB seed + explicit naive timestamp set in test setup (removes dependency on `/api/next` side effects)
  - isolated rerun sample after fix: `10/10` pass

## Batch B Impact
- Integration boundaries are cleaner (API flow vs harness utility tests).
- Repeated assertion/subprocess patterns are now centralized.
- Remaining simplification work can proceed with lower per-file refactor cost.
