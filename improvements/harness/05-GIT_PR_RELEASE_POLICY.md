# Git, PR, and Release Policy

This policy keeps high-velocity agentic work reviewable.

## Branch naming

Recommended:

- `chore/<item-slug>` for majors/minors
- `fix/<incident-or-bug-slug>` for urgent patches
- `spike/<question-slug>` for time-boxed research

## Commit conventions

Each commit should map to one cohesive step.

Recommended format:

- `<item-id>: <short summary>`

Examples:

- `47: demote compass to optional UI layer`
- `68: make place refresh best effort`

## Pull request requirements

Each PR should include:

- linked work item ID(s)
- scope summary
- changed files summary
- verification commands + outcomes
- risks and rollback notes

Use `templates/PR_EVIDENCE_TEMPLATE.md`.

## Merge strategy

Default:

- squash merge for minor/patch work.
- merge commit for larger majors when preserving intermediate history is useful.

## Release channels

Recommended:

- `dev`: high frequency integration
- `staging`: stabilization and acceptance
- `prod`: gated promotion only

## Promotion gates

Dev to staging:

- required quality gates pass
- no unresolved high-risk findings

Staging to prod:

- smoke tests pass in staging
- rollback plan validated
- incident owner assigned for release window

## Hotfix policy

For urgent regressions:

1. patch minimal blast radius first,
2. ship,
3. backfill root-cause hardening as tracked follow-up.

