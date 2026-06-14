# Quality Gates

Quality gates prevent fast delivery from degrading reliability.

## Gate categories

## Gate 0: Surface control and artifact hygiene

Checks:

- no unplanned parallel runtime path was introduced for existing behavior
- optional/harness behavior remains off the default validation/runtime path
- generated artifacts are stored in archive/history locations, not mixed into
  source-of-truth paths

Evidence:

- diff summary showing authoritative path touchpoints
- artifact location summary for new outputs

## Gate 1: Contract integrity

Checks:

- API routes and payload shapes remain stable unless approved.
- Event schemas and response envelopes remain compatible.
- CLI command surface remains backward-compatible or has explicit migration note.

Evidence:

- contract tests
- snapshot/schema checks

## Gate 2: Correctness

Checks:

- unit tests pass for touched modules
- integration tests pass for touched workflows
- critical path smoke tests pass
- pytest warning count stays at or below budget artifact threshold

Evidence:

- test command output summaries
- failed test list with disposition if any are quarantined

## Gate 3: Build and static health

Checks:

- project builds successfully
- lint/type/static analysis checks pass

Evidence:

- command + result summary

## Gate 4: Runtime behavior

Checks:

- no regressions in key latency paths
- error rate does not exceed budget
- memory/cache growth remains bounded

Evidence:

- baseline vs after metrics

## Gate 5: Operational safety

Checks:

- rollback path documented
- feature flag or safe disable path for risky changes
- migration rollback strategy documented for stateful changes

Evidence:

- rollback notes in item or PR evidence doc

## Gate 5a: v3 Sweep Evidence (required for lane-matrix or scoring changes)

Changes to lane/budget axes, sweep scoring, or composite-score weights must produce a reproducible
sweep manifest before merge.

Required fields in every `phase_a_summary.json`:

- `lane_budget_axes` — `llm_narrator_models`, `llm_referee_models`, `v3_projection_max_nodes_options`
- `seed_schedule` — deterministic list of int seeds, equal across all configs in the run
- `quality_gate_outcomes.shared_seed_schedule_validated: true`
- `quality_gate_outcomes.projection_quality_metrics_present: true`
- `projection_health_summary` — aggregate projection warning counts
- `clarity_ranked_results` — per-config clarity ranking

Secondary ranking views in `phase_a_summary.json` (must be present, may be empty list):

- `projection_ranked_results`
- `motif_ranked_results`
- `clarity_ranked_results`
- `latency_ranked_results`

Dry-run verification command (no live backend required):

```bash
python scripts/dev.py harness sweep --lane-matrix-preset v3-default --phase a --dry-run
```

Full integration test command:

```bash
pytest -q tests/integration/test_parameter_sweep_harness.py
```

Evidence:

- dry-run summary JSON with all required fields present
- 23 harness integration tests pass

## Merge policy by risk level

Low risk:

- Gate 0 + Gate 1 + Gate 2 + Gate 3 required.

Medium risk:

- All low-risk gates plus Gate 4.

High risk:

- All gates required, plus staged rollout plan.

## Gate 2a: v3 Projection Smoke (required for any v3-risk change)

Changes touching projection BFS, prefetch, commit/invalidation, or diagnostic envelopes must
pass this targeted smoke suite before merge.

Checks:

- Non-canon stubs are generated with `non_canon=True` and `projection_depth >= 1`
- Projection refresh does not mutate canonical session vars or create world events
- `invalidate_projection_for_session` clears the cached stub list to `[]`
- Every action/next response includes `_ww_diag` with `turn_source` and `pipeline_mode`

Command:

```bash
pytest -q tests/integration/test_turn_progression_simulation.py -k "v3_projection or v3_action"
```

Evidence:

- all four smoke tests pass with 0 failures
- `nodes_pruned`, `pressure_tier`, `budget_exhaustion_cause` present in `context_summary`

## Gate 6: Long-run Soak (required for projection/graph hardening items)

Soak scenarios run deterministically over multiple cycles using service-layer calls and
controlled seeds. They stress graph cleanliness, projection cache churn, and adaptive-pruning
telemetry without requiring a live LLM.

Checks:

- `projection_nodes_examined` never exceeds `v3_projection_max_nodes` across N refresh cycles
- Pressure expansion counters grow monotonically (one record per successful refresh)
- `total_nodes_pruned` in runtime metrics matches cumulative `nodes_pruned` from context_summary

Thresholds (pass/fail):

- Any `projection_nodes_examined > max_nodes` → soak gate fails
- `total_expansions != successful_cycles` → counter drift detected → gate fails
- `runtime_metrics.total_nodes_pruned != context_summary cumulative` → telemetry mismatch → gate fails

Command:

```bash
pytest -q tests/integration/test_turn_progression_simulation.py -k "soak"
```

Full integration command:

```bash
pytest -q tests/integration/test_turn_progression_simulation.py
```

Interpretation notes:

- `nodes_pruned=0` in every cycle with `adaptive_pruning=True` is expected when `prune_threshold`
  is above the observed pressure — this is correct behavior, not a gap.
- If `full_expansions` count is lower than `successful_cycles`, a refresh returned `None`
  (expansion disabled or feature flag off) — check monkeypatch values.
- `budget_exhaustion_cause=None` for cycles that never exhausted budget is correct.

## Suggested baseline commands

Project strict command path:

- `python scripts/dev.py quality-strict`

v3 projection smoke (Gate 2a):

- `pytest -q tests/integration/test_turn_progression_simulation.py -k "v3_projection or v3_action"`

v3 soak gate (Gate 6):

- `pytest -q tests/integration/test_turn_progression_simulation.py -k "soak"`

Project baseline commands:

- backend tests
- frontend tests/build
- contract tests
- lint/type checks
- smoke scripts
- command-surface sanity checks for touched CLIs

## Failure handling

If any required gate fails:

- do not mark item done,
- either fix immediately,
- or split remaining work into a follow-up item and keep current item in
  `verify` or `blocked`.
