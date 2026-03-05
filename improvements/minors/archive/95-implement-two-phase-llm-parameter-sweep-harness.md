# Minor 95: Implement two-phase LLM parameter sweep harness

## Problem Statement
The game exhibits semantic repetition (e.g. repeatedly referencing "ozone" or "morning sun") that cannot be fully cured by prompt engineering alone. A systematic sweep of LLM hyperparameters is needed to map the "pareto front" of creativity versus system coherence, without generating 500 manual runs.

## Scope Boundaries

- In scope: playtest harness orchestration, parameter-grid generation, run artifact emission, and command-surface integration.
- Out of scope: API contract changes, model-provider changes, and gameplay logic rewrites.

## Assumptions

- Sweep runs are executed against a local backend where env-var overrides can be applied per run.
- Comparative quality signals can be approximated with deterministic summary metrics (latency, prefix repetition, request failures) before manual narrative review.
- Existing long-run harness behavior should remain backwards compatible for non-sweep usage.

## Proposed Solution
Create a new developer script based on `long_run_harness.py` that automatically iterates over a provided Latin Hypercube of explicitly defined parameter variables.

- Extract reusable long-run execution logic from `long_run_harness.py` into a callable function and expose parameter-env mapping helpers.
- Implement `playtest_harness/parameter_sweep.py` with:
  - Phase A coarse sweep generation and execution (12-20 configs x 20 turns default),
  - Phase B ranking/selection summary that outputs top 3-5 candidate configurations,
  - structured artifact output under `playtests/sweeps`.
- Add a `python scripts/dev.py sweep ...` command wrapper for local parity.

### Acceptance Criteria
- [x] Extract the core loop of `long_run_harness.py` into a parameterized function that accepts:
  - `llm_temperature`
  - `llm_max_tokens` (or separate intent vs narration)
  - `llm_recency_penalty`
  - `llm_semantic_floor_probability`
- [x] Phase A (Coarse mapping): Run a fast 12-20 config grid (20 turns each) using local environment variables, writing outputs to `playtests/sweeps`.
- [x] Phase B (Deep analysis): Output basic metrics (latency, exact prefix matches, failure rates) for each seed to identify the top 3-5 configurations to run locally.

## Expected Files Changed
- `playtest_harness/parameter_sweep.py` (New file)
- `playtest_harness/long_run_harness.py`
- `scripts/dev.py` (Add new `sweep` command)
- `README.md`
- `improvements/ROADMAP.md`

## Validation Commands

- `python scripts/dev.py sweep --help`
- `python playtest_harness/parameter_sweep.py --phase a --dry-run`
- `python playtest_harness/parameter_sweep.py --phase b --phase-a-summary <path> --dry-run`
- `python scripts/dev.py quality-strict`

## Rollback Plan
- Delete `sweep` and revert `dev.py`.
