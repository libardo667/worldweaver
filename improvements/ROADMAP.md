# Roadmap

## Current State

- Product status: Core explore/action gameplay is functional with deterministic state commits, strict staged action orchestration, and baseline eval tooling; remaining work is coherence hardening and comparative playtest instrumentation.
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

1. [P1][Pending] `62-harden-world-memory-and-projection-spine-v2.md` (v2 spine acceptance after strict eval + playtest harness evidence).

## Minor Queue

1. [P1][Pending] `89-add-storylet-effects-contract-and-server-application.md`.
2. [P1][Pending] `95-implement-two-phase-llm-parameter-sweep-harness.md`.
3. [P1][Pending] `96-expand-static-quality-gates-to-tests-scripts-and-warning-budget.md`.

## Recommended Execution Order

1. Ship minor `89` to make storylet state effects deterministic, server-applied, and replayable.
2. Run major `62` v2 hardening with strict narrative eval and playtest harness evidence.
3. Ship minor `95` and run Phase A/B sweeps to choose comparative test configs.
4. Ship minor `96` to lock strict static/test warning hygiene before large comparative runs.
5. Start the next long playtest cycle only after steps 1-2 are complete; start comparative series after steps 1-4 are complete.

## Notes

- This roadmap is intentionally flattened to active work only; completed/history tracking remains in `improvements/history/` and archived item docs.
- Completed in this cycle: major `59` and major `69` (see PR evidence for combined closure).
- Completed in this cycle: minor `80` (structured logging + correlation IDs).
- Completed in this cycle: minor `84` (narrative eval coherence metric expansion).
- Completed in this cycle: minor `88` (primary-goal backfill after initial turn).
- Comparative playtests should be treated as optimization work, not discovery, and therefore follow metrics/tracing hardening first.
- Update this file in the same PR whenever item status changes.
