# Roadmap

## Current State

- Product status: Core explore/action gameplay is functional with deterministic state commits, strict staged action orchestration, and hardened v2 memory/projection eval gates; active work has shifted to harness latency correctness and comparative sweep fidelity.
- Architecture status: Major `69` (clean 3-layer LLM architecture) and major `59` (authoritative reducer/rulebook unification) are now complete, including persisted Scene Card "Now" state and reducer-routed `/next` var mutations.
- Top risks:
  - Parameter sweeps can produce noisy outcomes if backend conditions (model/key/env) are not held constant between runs.
  - Comparative ranking still relies on heuristic scoring and needs periodic calibration against narrative eval outcomes.

## Guardrails

1. No API route/path/payload contract changes unless explicitly approved.
2. Keep API layers thin and enforce all authoritative state mutation in services/reducer paths.
3. Do not mark items done without required quality gates (`python -m pytest -q`, `npm --prefix client run build`, and item-specific gates).
4. Prefer bounded, replayable, deterministic state transitions over implicit prompt-only behavior.
5. Every completed item must include PR evidence with risks, rollback notes, and validation output summaries.

## Major Queue

- None active.

## Minor Queue

- None active.

## Recommended Execution Order

1. Run a short verification sweep (`--phase-a-configs 2 --phase-a-turns 5`) and inspect `overhead_diagnostics` plus per-run prefetch metrics.
2. Resume full Phase A/B comparative sweeps and narrative eval ranking with the new metrics visibility.
3. Revisit scoring weights if request-latency and wall-clock leadership diverge.

## Notes

- This roadmap is intentionally flattened to active work only; completed/history tracking remains in `improvements/history/` and archived item docs.
- Completed in this cycle: major `59` and major `69` (see PR evidence for combined closure).
- Completed in this cycle: major `62` (v2 world-memory/projection spine hardening with strict eval acceptance).
- Completed in this cycle: minor `80` (structured logging + correlation IDs).
- Completed in this cycle: minor `84` (narrative eval coherence metric expansion).
- Completed in this cycle: minor `88` (primary-goal backfill after initial turn).
- Completed in this cycle: minor `89` (storylet effects contract + reducer-backed application).
- Completed in this cycle: minor `96` (strict static gates expanded to tests/scripts plus pytest warning budget enforcement).
- Completed in this cycle: minor `95` (two-phase LLM parameter sweep harness with dev command wrapper and ranked sweep artifacts).
- Completed in this cycle: minor `98` (prefetch status contract alignment in harness with bounded prefetch wait and regression coverage).
- Completed in this cycle: major `97` (sweep latency accounting hardening with explicit prefetch wait policy and overhead diagnostics).
- Comparative playtests should be treated as optimization work, not discovery, and therefore follow metrics/tracing hardening first.
- Update this file in the same PR whenever item status changes.
