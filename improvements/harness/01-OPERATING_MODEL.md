# Operating Model: Generative Sculpting

This model treats AI-assisted coding as two equally important motions:

- expansion (generate and ship)
- reduction (delete, merge, simplify)

## Core principles

1. Speed is useful only when behavior is measurable.
2. Every fast addition creates future pruning debt.
3. Optional features must not become implicit runtime dependencies.
4. Defaults should favor reliability over cleverness.
5. Deletion is a planned milestone, not cleanup day.

## Development phases

## Phase A: Generate

Purpose: ship a coherent end-to-end behavior quickly.

Rules:

- Prefer vertical slices over perfect abstractions.
- Accept temporary duplication when it buys clarity and speed.
- Add minimal instrumentation immediately.

Output:

- Working feature path.
- Known risk list.
- Initial acceptance criteria.

## Phase B: Stabilize

Purpose: lock behavior before broad optimization/refactor.

Rules:

- Freeze contracts (API, schema, events, CLI shape).
- Add deterministic tests for the critical path.
- Capture baseline latency/cost/error metrics.

Output:

- Stable contract envelope.
- Baseline measurements.
- Rollback-ready change boundary.

## Phase C: Prune

Purpose: reduce accidental complexity without behavioral regressions.

Rules:

- Remove dead branches and duplicate paths.
- Demote fragile subsystems to optional layers.
- Keep rollback notes for each deletion.

Output:

- Smaller runtime surface.
- Lower operational risk.
- Clearer ownership boundaries.

## Weekly cadence (recommended)

Monday to Wednesday:

- Generate and stabilize.

Thursday:

- Prune and simplify.

Friday:

- Retrospective and next-batch planning.

## Work-in-progress limits

- Max 1 active major per contributor/agent stream.
- Max 3 active minors per stream.
- No new major starts when stabilization gates are red.

## Completion definition

A change is done only when:

- acceptance criteria are checked,
- required tests pass,
- rollback path is documented,
- follow-up debt is captured as explicit new items.

