# Adoption Guide (Any Codebase)

Use this when you want to strap an agentic execution harness onto an existing
repo without rewriting how the team already works.

## Goal

Install a predictable build-fast, stabilize, prune loop in less than one day.

## Step 1: Copy harness files

Copy this `improvements/harness/` folder into the target repo.

Recommended destination:

- `improvements/harness/` for planning-first repos.
- `docs/agentic-harness/` for docs-first repos.

## Step 2: Establish project anchors

Create or confirm these project-specific anchors:

- `VISION.md` or equivalent product/architecture intent doc.
- `ROADMAP.md` or equivalent execution queue.
- Work item schemas (major/minor or equivalent).

If absent, start from templates in `templates/`.

## Step 3: Define the command surface

Document canonical commands for:

- setup/install
- run backend
- run frontend
- run tests
- run static checks
- run production-like local stack

The harness expects these commands to exist and stay stable.

## Step 4: Configure quality gates

Set required merge checks:

- unit/integration tests
- contract/API checks
- build/lint/type checks
- smoke path checks

Add project-specific thresholds (latency, cost, error budget) in
`04-QUALITY_GATES.md`.

## Step 5: Switch to item-driven execution

All changes should map to a tracked item:

- major for system-level or cross-cutting changes
- minor for low-risk focused improvements
- patch for urgent regressions
- incident for break/fix with postmortem
- spike for time-boxed research

## Step 6: Start weekly sculpting cadence

Adopt the loop:

1. Generate: ship behavior fast.
2. Stabilize: lock behavior with tests and contracts.
3. Prune: remove complexity and demote optional features.
4. Retrospective: record what to keep, what to cut, what to gate.

## Minimum successful install checklist

- [ ] Harness folder copied into repo.
- [ ] Vision and roadmap anchors linked from harness README.
- [ ] Canonical run/test/build commands documented.
- [ ] Merge quality gates enabled in CI.
- [ ] First week of work tracked through harness item taxonomy.

