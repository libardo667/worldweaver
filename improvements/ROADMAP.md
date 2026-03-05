# Roadmap

## Current State

- Product status: Core explore/action gameplay is functional with deterministic state commits, strict staged action orchestration, and hardened v2 memory/projection eval gates; remaining work is comparative playtest optimization/instrumentation.
- Architecture status: Major `69` (clean 3-layer LLM architecture) and major `59` (authoritative reducer/rulebook unification) are now complete, including persisted Scene Card "Now" state and reducer-routed `/next` var mutations.
- Top risks:
  - Long-run coherence quality still needs stricter eval metrics + parameter sweep evidence before comparative runs.
  - Comparative playtests will produce low-signal results until coherence metrics and correlation-aware tracing are tightened.

## Guardrails

1. No API route/path/payload contract changes unless explicitly approved.
2. Keep API layers thin and enforce all authoritative state mutation in services/reducer paths.
3. Do not mark items done without required quality gates (`python -m pytest -q`, `npm --prefix client run build`, and item-specific gates).
4. Prefer bounded, replayable, deterministic state transitions over implicit prompt-only behavior.
5. Every completed item must include PR evidence with risks, rollback notes, and validation output summaries.

## Major Queue

- None active.

## Minor Queue

1. [P1][Pending] `95-implement-two-phase-llm-parameter-sweep-harness.md`.

## Recommended Execution Order

1. Ship minor `95` and run Phase A/B sweeps to choose comparative test configs.
2. Start the next long playtest cycle after step 1; start comparative series after step 1 completes.

## Notes

- This roadmap is intentionally flattened to active work only; completed/history tracking remains in `improvements/history/` and archived item docs.
- Completed in this cycle: major `59` and major `69` (see PR evidence for combined closure).
- Completed in this cycle: major `62` (v2 world-memory/projection spine hardening with strict eval acceptance).
- Completed in this cycle: minor `80` (structured logging + correlation IDs).
- Completed in this cycle: minor `84` (narrative eval coherence metric expansion).
- Completed in this cycle: minor `88` (primary-goal backfill after initial turn).
- Completed in this cycle: minor `89` (storylet effects contract + reducer-backed application).
- Completed in this cycle: minor `96` (strict static gates expanded to tests/scripts plus pytest warning budget enforcement).
- Comparative playtests should be treated as optimization work, not discovery, and therefore follow metrics/tracing hardening first.
- Update this file in the same PR whenever item status changes.
