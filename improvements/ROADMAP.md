# Roadmap

## Current State

- Product status: Core explore/action gameplay is functional with deterministic state commits, strict staged action orchestration, and hardened v2 memory/projection eval gates; remaining work is comparative playtest optimization/instrumentation.
- Architecture status: Major `69` (clean 3-layer LLM architecture) and major `59` (authoritative reducer/rulebook unification) are now complete, including persisted Scene Card "Now" state and reducer-routed `/next` var mutations.
- Top risks:
  - Comparative playtests now depend on disciplined execution/review, not missing core architecture or harness features.
  - Parameter sweeps can produce noisy outcomes if backend conditions (model/key/env) are not held constant between runs.

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

1. Run a real (non-dry-run) Phase A/B sweep and select the top ranked 3-5 configs.
2. Start the next comparative long-playtest series using the selected configs and evaluate deltas with the narrative eval harness.

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
- Comparative playtests should be treated as optimization work, not discovery, and therefore follow metrics/tracing hardening first.
- Update this file in the same PR whenever item status changes.
