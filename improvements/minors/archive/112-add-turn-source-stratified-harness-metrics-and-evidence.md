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

## Implementation notes

### Fields added to per-run summaries (`long_run_harness.py`)

- `freeform_turns` — count of turns whose `action_source` starts with `"diversity"` (explicit alias for `diversity_turns`)
- `freeform_turn_pct` — fraction of choice+freeform turns that were freeform
- `choice_turn_pct` — fraction of choice+freeform turns that were choice-button
- `stratified_metrics` — dict with `"choice"` and `"freeform"` sub-dicts, each containing:
  - `turn_count` — number of turns in that source group
  - `latency_ms_avg` — average request latency for that group
  - `failure_rate` — fraction of turns that errored
  - `projection_hit_rate`, `projection_waste_rate`, `projection_veto_rate` — projection lane health per source
  - `clarity_level_distribution` — per-clarity-level counts for that source group

### Fields added to phase-level aggregates (`parameter_sweep.py`)

- `stratified_metrics` — same structure as per-run, with numeric fields averaged across runs and clarity distributions averaged per level

### Interpretation guidance

When `diversity_every` or `diversity_chance` is non-zero, sweep runs include a mix of freeform and choice-button turns. Stratified metrics reveal whether quality differences are driven by one source or the other:

- `freeform_turn_pct == 0.0` means no freeform turns were exercised; projection/clarity evidence is choice-only.
- Compare `choice.projection_hit_rate` vs `freeform.projection_hit_rate` to diagnose whether the projection lane is only helping one source.
- `freeform.failure_rate` significantly above `choice.failure_rate` suggests the action endpoint has different reliability characteristics.
