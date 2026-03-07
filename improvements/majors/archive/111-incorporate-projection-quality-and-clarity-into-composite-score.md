# Incorporate projection quality and clarity into composite score and sweep quality gates

## Problem

The v3 vision names projection quality (hit/waste/veto rates) and clarity level distribution as primary observable quality targets. The sweep harness already measures both, but the composite score used to rank configs and promote them from Phase A to Phase B ignores them entirely.

The current `score_run_metrics` formula in `parameter_sweep.py` is:

```
composite = (failure_rate × 0.55) + (prefix_repetition × 0.25) + (motif_reuse × 0.05) + (latency × 0.15)
```

Two consequences:

1. **Projection quality is invisible to config promotion.** The sweep data from the full dark fantasy sweep shows projection waste rates of 80–100% across all configs (only 0–20% of prefetched projections were ever selected at turn time). A config with 95% projection waste ranks identically to one with 20% waste — because the score ignores it. Phase B promotion selects the wrong configs from the perspective of the vision's goal of a "continuously prepared near-future frontier."

2. **Clarity distribution degeneration is undetected.** In the same sweep data, 80–100% of turns in every config ended at `unknown` clarity — meaning the projection system produced almost no `prepared` stubs that were actually consumed. The vision defines `prepared` as "scene-ready projection seed exists." If nothing ever reaches `prepared`, the projection lane is doing no useful work. No current gate catches this.

The `_projection_penalty_score` function exists and is used for a separate ranking view, but it is not wired into the main composite score or Phase B promotion criteria.

## Proposed Solution

### Phase 1: Add projection quality weight to composite score

1. In `parameter_sweep.py`, extend `score_run_metrics` to accept and incorporate projection quality:
   - Add `projection_hit_rate: float | None = None` and `projection_waste_rate: float | None = None` parameters (optional, defaulting to neutral values when not provided for backward compatibility).
   - Rebalance weights to make room for projection quality. Proposed redistribution:
     - failure component: 0.50 (from 0.55)
     - prefix repetition: 0.20 (from 0.25)
     - motif reuse: 0.05 (unchanged)
     - latency: 0.10 (from 0.15)
     - projection quality: 0.15 (new — derived from `_projection_penalty_score`)
   - When `projection_hit_rate` and `projection_waste_rate` are both `None`, the projection component defaults to neutral (0.5 penalty × 0.15 weight) so old callers are not affected.

2. Update all callers of `score_run_metrics` in `long_run_harness.py` to pass projection metrics from run results.

### Phase 2: Add clarity distribution penalty

1. Add a `clarity_score` helper in `parameter_sweep.py` that converts a clarity distribution dict to a quality signal:
   - Full `unknown` (all turns at unknown) → 0.0
   - Any `prepared` or higher turns → progressively higher score proportional to the fraction at `prepared`+`committed`
   - This score is used as an additive signal within the projection quality component, not a separate composite dimension (keep the composite to five components maximum).

2. The clarity score lowers the projection quality component when the clarity distribution is degenerate. This creates an incentive for configs to produce `prepared` projections, not just to avoid waste.

### Phase 3: Add Phase A quality gates for degenerate projection behavior

1. In `parameter_sweep.py`, add a `check_run_projection_health` function that returns a list of warning strings for a run:
   - Warn if `projection_waste_rate > 0.90` (projection prefetch is nearly never used)
   - Warn if clarity distribution has zero `prepared` or `committed` turns
   - Warn if `projection_hit_rate == 0.0` for a non-trivial run (>10 turns)

2. Include these warnings in Phase A per-run result records as `projection_health_warnings: list[str]`. They are informational only — they do not disqualify configs from Phase B — but they surface in the summary JSON for human review.

3. Add a `projection_health_summary` field to phase summaries that aggregates warnings across all configs, making degenerate projection behavior visible at a glance.

### Phase 4: Update ranking views

1. The existing `latency_ranked_results` and `motif_ranked_results` views in phase summaries now reflect the updated composite score.
2. The existing `projection_ranked_results` view (from `_rank_phase_results_by_projection_efficiency`) remains unchanged as a secondary lens.
3. Add a new `clarity_ranked_results` view that ranks configs by their clarity distribution (fraction of turns reaching `prepared` or higher), giving human reviewers a dedicated lens on projection utility.

### Phase 5: Update quality gate docs and test hardening

1. Update `improvements/harness/04-QUALITY_GATES.md` to document:
   - The updated composite score formula and component weights
   - The `projection_health_warnings` field and what each warning means
   - Minimum expectations for a sweep run to be considered evidence-quality
2. Add tests in `tests/integration/test_parameter_sweep_ranking.py` and `tests/integration/test_parameter_sweep_metrics.py` verifying:
   - `score_run_metrics` output changes appropriately when projection quality is provided vs. absent
   - `clarity_score` returns 0.0 for all-unknown distributions and >0.0 for any prepared turns
   - Phase summary includes `projection_health_warnings` and `clarity_ranked_results` fields

## Files Affected

- `playtest_harness/parameter_sweep.py` — `score_run_metrics`, `clarity_score`, `check_run_projection_health`, `clarity_ranked_results`
- `playtest_harness/long_run_harness.py` — pass projection metrics to `score_run_metrics`
- `improvements/harness/04-QUALITY_GATES.md` — document updated composite formula and projection health gates
- `tests/integration/test_parameter_sweep_ranking.py` — composite score projection tests
- `tests/integration/test_parameter_sweep_metrics.py` — clarity score and projection health warning tests

## Acceptance Criteria

- [ ] `score_run_metrics` accepts `projection_hit_rate` and `projection_waste_rate`; they affect composite score output when provided.
- [ ] Existing callers that omit projection params produce neutral (not errored) composite scores.
- [ ] `clarity_score` returns 0.0 for all-unknown distributions and a positive value for any `prepared`/`committed` turns.
- [ ] Phase A per-run results include `projection_health_warnings` list.
- [ ] Phase summaries include `projection_health_summary` and `clarity_ranked_results` fields.
- [ ] `improvements/harness/04-QUALITY_GATES.md` documents updated composite formula and projection health fields.
- [ ] Integration tests pass for composite score with and without projection params, clarity score, and new summary fields.
- [ ] `python scripts/dev.py quality-strict` passes.

## Risks & Rollback

- Risk: Rebalancing composite score weights changes ranking order for existing sweep results. Historical comparisons across sweeps run before and after this change will not be directly comparable.
- Risk: Adding projection quality to the composite score may depress composite scores for all configs until projection hit rates improve — making it harder to track progress on other quality dimensions.
- Rollback: Restore original `score_run_metrics` weights and remove `projection_hit_rate`/`projection_waste_rate` parameters. The new `projection_health_warnings` and `clarity_ranked_results` fields are additive to the summary JSON and can remain in place without affecting existing consumers.
