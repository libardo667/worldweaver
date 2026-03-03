# Work Item System

This system standardizes planning so agents can execute with low ambiguity.

## Item types

## Major

Use for:

- multi-file system changes
- architecture moves
- behavior changes spanning services/UI/data

Required:

- full problem statement
- affected files list
- acceptance checklist
- risks and rollback plan

## Minor

Use for:

- focused low-risk improvements
- single-surface fixes
- documentation and tooling polish

Required:

- clear scope boundary
- acceptance checklist

## Patch

Use for:

- urgent regressions
- production-impacting defects

Required:

- incident context
- immediate fix
- follow-up hardening item

## Incident

Use for:

- outages
- data integrity breaks
- severe security/reliability events

Required:

- timeline
- blast radius
- root cause
- permanent prevention steps

## Spike

Use for:

- time-boxed research
- uncertainty reduction

Required:

- max time budget
- explicit decision output
- no hidden production changes

## Status model

Use one of:

- `backlog`
- `ready`
- `in_progress`
- `blocked`
- `verify`
- `done`
- `archived`

## Metadata fields (recommended)

- `id`
- `title`
- `type`
- `owner`
- `created_at`
- `target_window`
- `risk_level` (`low`, `medium`, `high`)
- `touch_areas` (api, ui, db, infra, docs)
- `depends_on`
- `supersedes`

## Entry and exit rules

Entry to `in_progress`:

- scope is explicit,
- acceptance criteria exist,
- validation commands are listed.

Exit to `done`:

- acceptance criteria checked,
- validation evidence attached,
- rollback notes present,
- follow-ups created when needed.

