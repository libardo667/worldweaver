# PR Evidence: Minor 95 - Implement Two-Phase LLM Parameter Sweep Harness

## Item

`improvements/minors/archive/95-implement-two-phase-llm-parameter-sweep-harness.md`

## Scope

Implemented a reusable two-phase sweep workflow for LLM runtime tuning:

- extracted and parameterized long-run harness execution logic,
- added Phase A coarse mapping and Phase B ranked seed-analysis orchestration,
- wired a `scripts/dev.py sweep` command path,
- documented usage and updated active roadmap status.

## What Changed

| File | Change |
|------|--------|
| `playtest_harness/long_run_harness.py` | Extracted reusable `run_long_playtest(...)` + `persist_run_payload(...)`; added explicit LLM parameter fields (`llm_temperature`, `llm_max_tokens`, `llm_recency_penalty`, `llm_semantic_floor_probability`); added env-override mapping helpers; added per-request latency/failure tracking and exact-prefix repetition summary metrics. |
| `playtest_harness/parameter_sweep.py` | Added new two-phase sweep harness with Latin-hypercube Phase A config generation, Phase B top-candidate multi-seed analysis, ranking/scoring, structured artifact emission, dry-run mode, and optional per-config backend spawning using env overrides. |
| `scripts/dev.py` | Added `sweep` command passthrough to `playtest_harness/parameter_sweep.py`. |
| `tests/integration/test_parameter_sweep_harness.py` | Added deterministic unit coverage for sweep grid generation bounds, ranking behavior, env override formatting, and Phase A dry-run planning output. |
| `README.md` | Added `scripts/dev.py sweep` task-surface/validation command documentation. |
| `improvements/ROADMAP.md` | Marked minor `95` complete and flattened active minor queue to none. |
| `improvements/minors/archive/95-implement-two-phase-llm-parameter-sweep-harness.md` | Archived completed item and checked acceptance criteria. |

## Why This Matters

- It turns parameter tuning from ad-hoc/manual playtest runs into a repeatable, artifact-producing process.
- It gives explicit metrics for tradeoff decisions (latency, repetition, failure rate) before expensive long comparative series.
- It separates fast coarse exploration (Phase A) from focused deeper confirmation (Phase B), so tuning cost stays bounded.
- It enables controlled local sweeps via env overrides per config without changing API contracts.

## Acceptance Criteria Check

- [x] Core long-run loop extracted into parameterized function with required knobs.
- [x] Phase A coarse sweep supports 12-20 config mapping and writes artifacts under `playtests/sweeps`.
- [x] Phase B outputs per-seed latency/prefix/failure metrics and produces ranked top candidate set.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No API route/path/payload contract changes.
- All changes are harness/dev-command/test/documentation scope.

### Gate 2: Correctness

- `python -m pytest tests/integration/test_parameter_sweep_harness.py -q` -> `4 passed`
- `python scripts/dev.py quality-strict` -> pass (`552 passed, 14 warnings`; warning budget pass)

### Gate 3: Build and Static Health

- `python scripts/dev.py sweep --help` -> pass
- `python playtest_harness/parameter_sweep.py --phase a --dry-run` -> pass
- `python playtest_harness/parameter_sweep.py --phase b --phase-a-summary playtests/sweeps/20260305t065028z/phase_a_summary.json --dry-run` -> pass
- `python scripts/dev.py quality-strict` -> pass (includes lint/build/compileall + pytest warning-budget enforcement)

## Operational Safety / Rollback

- Rollback path: revert this PR's harness/dev/docs/test/roadmap changes; remove `playtest_harness/parameter_sweep.py` and restore pre-extraction `long_run_harness.py`.
- Safe-disable path: stop using `scripts/dev.py sweep` and keep existing long-run/manual harness flow unchanged.
- Data/migration impact: none (artifacts only under `playtests/sweeps`).

## Residual Risk

- Ranking is currently heuristic and metric-weighted; narrative-quality final selection still needs human review.
- Spawned-backend mode assumes local environment readiness (API key/model/config consistency) for stable comparative results.
