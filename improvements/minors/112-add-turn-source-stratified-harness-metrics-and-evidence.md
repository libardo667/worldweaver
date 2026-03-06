# Add turn-source stratified harness metrics and evidence

## Problem
Current harness metrics aggregate turn outcomes without consistently stratifying by action source (`choice_button` vs freeform). This can hide quality differences caused by the split orchestration paths and make sweep interpretation noisy when diversity/freeform rates change.

## Proposed Solution
Add additive stratified metrics to harness summaries and evidence artifacts.

1. Extend harness summaries to include per-source slices for key metrics:
   - latency,
   - failure rate,
   - projection hit/waste/veto,
   - clarity and fallback distributions.
2. Add explicit action-source mix telemetry:
   - percent choice turns,
   - percent freeform turns.
3. Update quality-gate evidence expectations for sweeps to include action-source mix and stratified metrics when diversity/freeform is enabled.

## Files Affected
- `playtest_harness/long_run_harness.py`
- `playtest_harness/parameter_sweep.py`
- `tests/integration/test_parameter_sweep_metrics.py`
- `tests/integration/test_parameter_sweep_harness.py`
- `improvements/harness/04-QUALITY_GATES.md`

## Acceptance Criteria
- [ ] Harness run summaries include action-source mix and stratified metric sections.
- [ ] Sweep phase summaries propagate these additive fields.
- [ ] Existing summary consumers remain backward compatible.
- [ ] Integration tests validate field shape and deterministic presence.

## Validation Commands
- `pytest -q tests/integration/test_parameter_sweep_metrics.py tests/integration/test_parameter_sweep_harness.py`
- `python scripts/dev.py quality-strict`

## Risks & Rollback
- Risk: summary payload bloat may make artifacts harder to skim.
- Rollback: keep aggregate metrics; gate stratified payload behind optional flag while preserving schema compatibility.
