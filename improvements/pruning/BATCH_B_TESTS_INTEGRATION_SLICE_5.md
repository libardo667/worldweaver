# Batch B Tests Integration Slice 5

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue large-slice simplification of `tests_integration` by decomposing the largest remaining test module.
- Improve maintainability by splitting parameter-sweep integration coverage into focused modules and shared payload/assert helpers.

## Changes
1. Split monolithic parameter-sweep integration test file by concern:
- removed `tests/integration/test_parameter_sweep_harness.py`
- added:
  - `tests/integration/test_parameter_sweep_ranking.py`
  - `tests/integration/test_parameter_sweep_phase_a.py`
  - `tests/integration/test_parameter_sweep_prefetch_reset.py`
  - `tests/integration/test_parameter_sweep_metrics.py`

2. Expanded shared harness helpers to reduce repeated payload boilerplate:
- `tests/integration_harness_helpers.py`
  - `PARAMETER_SWEEP_DEFAULT_PARAMETERS`
  - `build_phase_result(...)`
  - `assert_metric_values(...)`

3. Preserved existing integration coverage semantics while improving test-module boundaries:
- ranking/scoring tests grouped together
- phase-a dry-run tests grouped together
- prefetch/reset policy tests grouped together
- metrics aggregation/repetition tests grouped together

## Guardrail Verification
Commands:
- `ruff check tests/integration_harness_helpers.py tests/integration/test_parameter_sweep_ranking.py tests/integration/test_parameter_sweep_phase_a.py tests/integration/test_parameter_sweep_prefetch_reset.py tests/integration/test_parameter_sweep_metrics.py tests/integration/test_narrative_eval_harness.py`
- `pytest -q tests/integration`
- `python scripts/dev.py quality-strict`

Results:
- Lint: pass
- Integration suite: `45 passed`
- Full strict gate: pass (`583 passed`; warning budget unchanged)
- Note: one transient known flaky failure appeared on first strict run in `tests/service/test_storylet_selector.py::test_sparse_context_triggers_runtime_synthesis`; isolated rerun passed and strict rerun passed.

## Batch B Impact
- The largest integration test file is now decomposed into focused modules with shared builders/assertions.
- This is a high-yield simplification slice that lowers future edit risk and speeds continued pruning work.
