# Minor 95: Implement two-phase LLM parameter sweep harness

## Problem Statement
The game exhibits semantic repetition (e.g. repeatedly referencing "ozone" or "morning sun") that cannot be fully cured by prompt engineering alone. A systematic sweep of LLM hyperparameters is needed to map the "pareto front" of creativity versus system coherence, without generating 500 manual runs.

## Proposed Solution
Create a new developer script based on `long_run_harness.py` that automatically iterates over a provided Latin Hypercube of explicitly defined parameter variables.

### Acceptance Criteria
- [ ] Extract the core loop of `long_run_harness.py` into a parameterized function that accepts:
  - `llm_temperature`
  - `llm_max_tokens` (or separate intent vs narration)
  - `llm_recency_penalty`
  - `llm_semantic_floor_probability`
- [ ] Phase A (Coarse mapping): Run a fast 12-20 config grid (20 turns each) using local environment variables, writing outputs to `playtests/sweeps`.
- [ ] Phase B (Deep analysis): Output basic metrics (latency, exact prefix matches, failure rates) for each seed to identify the top 3-5 configurations to run locally.

## Expected Files Changed
- `playtest_harness/parameter_sweep.py` (New file)
- `scripts/dev.py` (Add new `sweep` command)

## Rollback Plan
- Delete `sweep` and revert `dev.py`.
