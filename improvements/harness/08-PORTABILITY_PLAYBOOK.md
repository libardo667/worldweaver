# Portability Playbook

Use this map to adapt the harness to different repository shapes.

## Single backend service repo

Prioritize:

- API contract tests
- migration safety
- latency instrumentation
- release rollback steps

De-emphasize:

- frontend build gates

## Frontend-only repo

Prioritize:

- type/build/lint gates
- visual regression snapshots
- interaction smoke tests
- performance budgets for critical routes

De-emphasize:

- DB/migration runbooks

## Full-stack monorepo

Prioritize:

- per-surface ownership boundaries
- cross-surface contract tests
- workspace-level command surface
- staged integration gates

## Data/ML-heavy repo

Prioritize:

- reproducibility gates
- dataset/version lineage
- experiment tracking
- model cost and latency budgets

## Infra/platform repo

Prioritize:

- safety and rollback automation
- change windows
- blast radius estimation
- incident response templates

## Minimal port checklist

- [ ] Update command references to target repo commands.
- [ ] Update quality gates to target repo CI checks.
- [ ] Update item templates with project naming conventions.
- [ ] Link harness index from project docs root.
- [ ] Run one full major and one full minor through the harness flow.

