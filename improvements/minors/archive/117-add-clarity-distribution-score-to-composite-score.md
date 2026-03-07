# Add clarity_distribution_score to composite score

## Problem

The composite score used by `score_run_metrics` (and therefore by Phase B candidate selection) does not include `clarity_distribution_score`. Clarity is the V3 vision's own vocabulary for Pillar 3 (Prepared frontier) — the distribution of `unknown` → `rumor` → `lead` → `prepared` → `committed` turns is the most direct observable measure of whether the "Weave ahead" step is producing usable seeds.

Phase A of the v3_true_first_sweep showed this gap concretely: a02 was the only config with a working projection lane (`projection_stub_count=5`, `projection_hit_rate=0.417`, `clarity_distribution_score=0.65`), but its composite score (0.801) was only 5–7 points above non-functioning configs (0.730–0.746). Clarity's absence from the composite means Phase B selection is not strongly incentivized by the most important V3 quality signal.

Clarity is tracked in a separate ranking view (`_rank_phase_results_by_clarity`) but contributes zero weight to the composite score used for Phase B promotion.

## Proposed Solution

Add `clarity_distribution_score` as a weighted component to `score_run_metrics`. Redistribute weights to maintain a total of 1.0:

```
Old:
  failure:    0.50
  repetition: 0.20
  motif:      0.05
  latency:    0.10
  projection: 0.15

New:
  failure:    0.50  (unchanged — gate metric, dominates correctly)
  repetition: 0.20  (unchanged — scene grounding pillar 1)
  motif:      0.05  (unchanged — secondary signal)
  latency:    0.05  (reduced — latency matters less than frontier quality)
  projection: 0.10  (reduced — efficiency signal, complements clarity)
  clarity:    0.10  (new — direct Pillar 3 signal, V3 vision vocabulary)
```

Rationale for redistribution:
- Latency 0.10 → 0.05: Phase A showed that higher latency (a02: 19s) is acceptable when projection is working. Penalizing latency too heavily would disadvantage the very configs that deliver projection value.
- Projection 0.15 → 0.10: Projection efficiency (hit/waste rates) and clarity distribution are related but distinct. Clarity directly measures "did the frontier advance?"; projection measures "was the advance used?" Together they receive 0.20 weight, appropriate for Pillar 3.
- Clarity 0.10 (new): Weighted as `clarity_distribution_score` directly (already in [0, 1], higher = better).

When `clarity_distribution_score` is None or absent (old callers / pre-minor-115 runs), it defaults to 0.5 (neutral) — same backward-compat convention as `projection_component`.

## Files Affected

- `playtest_harness/parameter_sweep.py` — `score_run_metrics` signature and weights; `rank_phase_results` passes clarity; Phase B composite scoring passes clarity from aggregated metrics
- `improvements/harness/10-SWEEP_METRICS_RUBRIC.md` — update composite score formula documentation

## Acceptance Criteria

- [ ] `score_run_metrics` accepts `clarity_distribution_score: float | None = None`.
- [ ] When `clarity_distribution_score=0.65` (a02's value), the composite score is higher than without it at the same other inputs.
- [ ] When `clarity_distribution_score=None`, result equals the pre-minor score (backward compat neutral default).
- [ ] `rank_phase_results` passes `clarity_distribution_score` from per-run metrics.
- [ ] Phase B `composite_score` computation passes clarity from aggregated metrics.
- [ ] `10-SWEEP_METRICS_RUBRIC.md` composite score formula reflects the new weights.
- [ ] `python scripts/dev.py quality-strict` passes.
