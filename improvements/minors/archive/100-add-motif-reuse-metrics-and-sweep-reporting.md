# Minor 100: Add motif reuse metrics and sweep reporting

## Metadata

- ID: 100-add-motif-reuse-metrics-and-sweep-reporting
- Type: minor
- Owner: levi
- Status: proposed
- Risk: low
- Depends On: 99-enforce-scene-card-grounded-narration-and-motif-governance

## Problem

Current sweep scoring tracks exact prefix repetition but does not capture semantic motif reuse. This hides motif gravity regressions where wording changes slightly but sensory anchors repeat heavily.

Without a motif-level metric, parameter ranking can overvalue low-latency configs that still produce repetitive atmosphere.

## Proposed Solution

Add motif reuse telemetry as a first-class sweep metric.

Scope:

1. Compute per-run motif overlap across turns:
   - motif token overlap count,
   - motif reuse rate (for example reused motifs / total motifs),
   - optional turn-local motif novelty score.
2. Persist motif metrics in long-run JSON summary and markdown report.
3. Surface motif metrics in phase summaries (`phase_a_summary.json`, `phase_b_summary.json`) and ranking views.
4. Optionally include motif reuse in composite score (weight configurable; default conservative).
5. Add regression tests for summary schema fields and ranking stability when motif metrics are present.

## Files Affected

- `playtest_harness/long_run_harness.py`
- `playtest_harness/parameter_sweep.py`
- `tests/integration/test_parameter_sweep_harness.py`
- `tests/integration/test_turn_progression_simulation.py`

## Acceptance Criteria

- [ ] Run summaries include motif reuse metrics alongside prefix repetition metrics.
- [ ] Phase A/B summaries aggregate motif reuse metrics per config.
- [ ] Ranking output surfaces motif metrics for top candidates.
- [ ] Existing summary consumers remain backward compatible (new fields additive).
- [ ] Integration tests assert motif metric presence and type stability.

## Validation Commands

- `python -m pytest -q tests/integration/test_parameter_sweep_harness.py`
- `python -m pytest -q tests/integration/test_turn_progression_simulation.py`
- `python scripts/dev.py sweep --phase a --phase-a-configs 2 --phase-a-turns 5`

