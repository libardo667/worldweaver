# Add clarity distribution as a sweep quality gate

## Problem

The v3 vision defines five clarity levels (`unknown` → `rumor` → `lead` → `prepared` → `committed`) as the primary measure of how useful the projection system is during a session. `prepared` means "a scene-ready projection seed exists for the next turn." If turns regularly reach `prepared`, the narrator can render from a pre-computed seed instead of cold-generating — which is the core latency and coherence benefit of the v3 projection architecture.

The sweep harness already tracks clarity distribution per run (as a dict of `{level: count}`). However:

1. There is no quality gate that flags when clarity distribution is degenerate. In the full dark fantasy sweep, 80–100% of turns ended at `unknown` across all configs — meaning the projection system produced effectively zero useful `prepared` seeds. This pattern went completely undetected by the sweep's summary and ranking logic.

2. The current `clarity_level_distribution` field appears in per-run metrics but is not aggregated or surfaced as a summary-level signal. Human reviewers must manually inspect each run's dict to notice degeneration.

3. Nothing in the existing quality gate docs (`04-QUALITY_GATES.md`) defines what a "good" or "bad" clarity distribution looks like, leaving sweep evidence interpretation informal.

## Proposed Solution

1. In `parameter_sweep.py`, add a `clarity_distribution_score` helper that takes a clarity distribution dict and returns a float in [0, 1]:
   - Score is the fraction of turns at `prepared` or higher (`prepared` + `committed` / total turns).
   - Turns at `unknown` contribute 0. Turns at `rumor` or `lead` contribute partial credit (e.g., 0.25 and 0.5 respectively) to avoid a cliff edge.
   - This score is already needed by major 111 for its clarity-aware projection quality component; this minor provides the standalone function and gate logic independently.

2. Add a `clarity_health_check` function that returns a warning string (or empty string) for a run:
   - Warning if `clarity_distribution_score < 0.05` (fewer than 5% of turns reached `prepared` or above)
   - Warning if every turn is at `unknown` (zero non-unknown turns)

3. In `long_run_harness.py`, call `clarity_health_check` per run and include the result in the run record as `clarity_health_warning: str`. Empty string means no issue.

4. In phase summaries, add a `clarity_distribution_score_avg` field (average across all runs in the phase) and a `clarity_health_flags` list (all non-empty `clarity_health_warning` values across runs with their config IDs).

5. Update `improvements/harness/04-QUALITY_GATES.md` with:
   - Definition of `clarity_distribution_score` and how it is computed
   - Minimum acceptable threshold: `clarity_distribution_score_avg >= 0.05` for a sweep run to be considered projection-lane evidence
   - Description of `clarity_health_flags` and what they indicate

## Files Affected

- `playtest_harness/long_run_harness.py` — `clarity_distribution_score`, `clarity_health_check`, `CLARITY_HEALTH_THRESHOLD`; per-run `clarity_distribution_score` and `clarity_health_warning` in summary dict
- `playtest_harness/parameter_sweep.py` — imports helpers; `_aggregate_phase_b_metrics` adds `clarity_distribution_score_avg`; `_clarity_gate_outcomes` adds phase-level `clarity_distribution_score_avg` and `clarity_health_flags` to `quality_gate_outcomes`
- `improvements/harness/10-SWEEP_METRICS_RUBRIC.md` — comprehensive metrics reference including clarity gate definition and threshold

Note: functions were placed in `long_run_harness.py` rather than `parameter_sweep.py` as originally specified, to avoid circular imports (`parameter_sweep.py` imports from `long_run_harness.py`).

## Acceptance Criteria

- [ ] `clarity_distribution_score` returns 0.0 for all-unknown distributions and > 0.0 for any `prepared`/`committed` turns.
- [ ] `clarity_health_check` returns a non-empty warning for configs where `clarity_distribution_score < 0.05`.
- [ ] Per-run records include `clarity_health_warning` field.
- [ ] Phase summaries include `clarity_distribution_score_avg` and `clarity_health_flags` fields.
- [ ] `04-QUALITY_GATES.md` documents the clarity gate threshold and field semantics.
- [ ] `python scripts/dev.py quality-strict` passes.
