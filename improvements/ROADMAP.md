# Roadmap

## Current State

- Product status: Core explore/action gameplay is functional with deterministic state commits and baseline eval tooling; long-run narrative coherence still needs stricter architecture enforcement before the next heavy playtest cycle.
- Architecture status: Most reducer + staged pipeline foundations are in place, but strict end-to-end 3-layer enforcement (Planner -> Reducer -> Narrator) is not yet complete across all turn paths.
- Top risks:
  - Long-run coherence drift and state sprawl without fully authoritative 3-layer boundaries and persisted canonical Scene Card "Now" state.
  - Comparative playtests will produce low-signal results until coherence metrics and correlation-aware tracing are tightened.

## Guardrails

1. No API route/path/payload contract changes unless explicitly approved.
2. Keep API layers thin and enforce all authoritative state mutation in services/reducer paths.
3. Do not mark items done without required quality gates (`python -m pytest -q`, `npm --prefix client run build`, and item-specific gates).
4. Prefer bounded, replayable, deterministic state transitions over implicit prompt-only behavior.
5. Every completed item must include PR evidence with risks, rollback notes, and validation output summaries.

## Major Queue

1. [P1][Pending] `69-implement-clean-3-layer-llm-architecture.md` (strict Planner -> Reducer -> Narrator pipeline, persisted Scene Card "Now", bounded growth enforcement).
2. [P1][Pending] `59-introduce-authoritative-event-reducer-and-rulebook.md` (close remaining non-reducer mutation paths, especially `/next` var writes).
3. [P1][Pending] `62-harden-world-memory-and-projection-spine-v2.md` (v2 spine acceptance after strict eval + playtest harness evidence).

## Minor Queue

1. [P1][Pending] `80-add-structured-logging-and-request-correlation-ids.md`.
2. [P1][Pending] `84-extend-narrative-eval-harness-with-coherence-metrics.md`.
3. [P1][Pending] `88-backfill-primary-goal-when-empty-after-initial-turn.md`.
4. [P1][Pending] `89-add-storylet-effects-contract-and-server-application.md`.
5. [P1][Pending] `95-implement-two-phase-llm-parameter-sweep-harness.md`.
6. [P1][Pending] `96-expand-static-quality-gates-to-tests-scripts-and-warning-budget.md`.

## Recommended Execution Order

1. Complete major `69` fully, including strict contract enforcement and persisted per-turn Scene Card "Now".
2. Close major `59` reducer-authority gaps so all persistent mutations flow through one rulebook path.
3. Ship minor `80` for correlation IDs and structured request lifecycle tracing.
4. Ship minor `84` so contradiction/arc-adherence coherence is measured and gated.
5. Ship minor `88` to prevent empty-goal drift in early turns.
6. Ship minor `89` to make storylet state effects deterministic, server-applied, and replayable.
7. Run major `62` v2 hardening with strict narrative eval and playtest harness evidence.
8. Ship minor `95` and run Phase A/B sweeps to choose comparative test configs.
9. Ship minor `96` to lock strict static/test warning hygiene before large comparative runs.
10. Start the next long playtest cycle only after steps 1-7 are complete; start comparative series after steps 1-9 are complete.

## Notes

- This roadmap is intentionally flattened to active work only; completed/history tracking remains in `improvements/history/` and archived item docs.
- Major `69` is the hard prerequisite for the next serious long run.
- Comparative playtests should be treated as optimization work, not discovery, and therefore follow metrics/tracing hardening first.
- Update this file in the same PR whenever item status changes.
