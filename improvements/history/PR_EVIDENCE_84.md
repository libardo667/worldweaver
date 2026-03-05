# PR Evidence: Minor 84 - Extend Narrative Eval Harness with Coherence Metrics

## Item

`improvements/minors/archive/84-extend-narrative-eval-harness-with-coherence-metrics.md`

## Scope

Extended the deterministic narrative evaluation harness with additive coherence metrics for contradiction detection, goal/arc adherence, and repetition-window guarding.

## What Changed

| File | Change |
|------|--------|
| `scripts/eval_narrative.py` | Added new metrics and signal collection: `contradiction_free_score`, `contradiction_frequency`, `arc_adherence_score`, `repetition_window_guard_score`, `repetition_window_violation_rate`; added state/history/graph-fact sampling per scenario and detailed metric breakdowns in report output. |
| `tests/integration/narrative_eval_scenarios.json` | Added `arc_expectations` metadata to goal-bearing scenarios so arc-adherence drift can be measured deterministically. |
| `reports/narrative_eval/baseline.json` | Added threshold entries for new guarded metrics (`arc_adherence_score`, `contradiction_free_score`, `repetition_window_guard_score`). |
| `tests/integration/test_narrative_eval_harness.py` | Extended smoke assertions to require presence of new metric keys. |
| `improvements/ROADMAP.md` | Marked minor `84` completed and removed from pending minor queue. |

## Why This Matters

- It closes a major observability gap before long/comparative playtests: coherence regressions are now directly measurable instead of inferred from aggregate success rates.
- Contradiction and arc-drift checks make narrative quality gates more aligned with product intent in `VISION.md` (world memory consistency + goal continuity).
- Repetition-window guarding catches short-horizon loopiness that simple adjacent-turn repetition checks can miss.

## Acceptance Criteria Check

- [x] Harness emits contradiction and arc-adherence metrics in `latest.json`.
- [x] Baseline threshold file includes the new metrics.
- [x] Smoke harness test validates presence of new metric keys.
- [x] `python scripts/dev.py eval-smoke` passes with enforcement enabled.

## Quality Gate Evidence

### Gate 2: Correctness

- `python scripts/dev.py eval-smoke` -> pass (no regressions under enforce)
- `python -m pytest tests/integration/test_narrative_eval_harness.py -q` -> `1 passed`
- `python -m pytest -q` -> `539 passed, 14 warnings`

### Gate 3: Build and Static Health

- `python scripts/dev.py lint-all` -> pass
- `npm --prefix client run build` -> pass

## Operational Safety / Rollback

- Rollback path: revert this PR’s eval-harness/script + baseline/scenario/test changes.
- No API contract modifications and no DB migration/state schema changes were introduced.

## Residual Risk

- Contradiction detection is heuristic and intentionally low-cost; it is directional and can miss nuanced semantic contradictions.
- Arc adherence relies on available persisted arc/goal signals and should be interpreted alongside qualitative playtest review.
