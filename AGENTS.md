# AGENTS.md

This is the project-level agent operating lookbook for WorldWeaver.

Use it as the default workflow policy for coding agents in this repository.

## Authority Order

When instructions conflict, apply this order:

1. Explicit task item scope and acceptance criteria (`improvements/majors/*`,
   `improvements/minors/*`).
2. Project anchors:
   - `improvements/VISION.md`
   - `improvements/ROADMAP.md`
3. Harness policy:
   - `improvements/harness/README.md`
   - `improvements/harness/02-WORK_ITEM_SYSTEM.md`
   - `improvements/harness/03-AGENT_EXECUTION_PROTOCOL.md`
   - `improvements/harness/04-QUALITY_GATES.md`
   - `improvements/harness/05-GIT_PR_RELEASE_POLICY.md`
   - `improvements/harness/07-PRUNING_PLAYBOOK.md`
   - `improvements/harness/09-PRUNING_PREVENTION_STANDARDS.md`
4. Harness templates for evidence formatting:
   - `improvements/harness/templates/AGENT_TASK_BRIEF_TEMPLATE.md`
   - `improvements/harness/templates/MAJOR_ITEM_TEMPLATE.md`
   - `improvements/harness/templates/MINOR_ITEM_TEMPLATE.md`
   - `improvements/harness/templates/PR_EVIDENCE_TEMPLATE.md`

Schema note:

- If repo-local work-item schemas define required sections, those local schemas
  remain authoritative over harness templates.

## Required Pre-Implementation Read Set

Before any implementation, read:

1. The active item doc (major or minor).
2. `improvements/VISION.md`.
3. `improvements/ROADMAP.md`.
4. The harness policy docs listed above.
5. Any touched-area contract docs or tests relevant to the item.

## Mandatory Declaration Before Coding

Before writing code, explicitly state:

1. Authoritative path being extended (module/route/component).
2. Default-path impact (`none`, `optional_only`, `core_path`).
3. Contract and compatibility impact (API, CLI, schema, event envelope).
4. Artifact output location (source-of-truth vs archive/history path).
5. Validation commands, including `python scripts/dev.py quality-strict` for
   non-trivial changes.

## Execution Rules (Pruning-Prevention)

- Extend existing authoritative paths; do not create unbounded parallel paths.
- Keep optional or harness workflows off the default runtime/validation path.
- Prefer behavior-preserving extractions before behavior changes.
- Avoid package-level patch/re-export coupling when concrete ownership imports
  are available.
- Any temporary compatibility shim must include explicit expiry/removal
  condition.
- Keep diffs bounded to declared scope; no drive-by refactors.

## Quality and Evidence Requirements

- Required gate baseline for non-trivial changes:
  - `python scripts/dev.py quality-strict`
- Run targeted tests and smoke checks for touched surfaces.
- If any required command is blocked, record why, add nearest substitute
  evidence, and do not mark work done.
- PR/work evidence must include:
  - authoritative path statement,
  - contract/CLI compatibility note,
  - artifact placement note,
  - rollback path.

## Artifact Placement Policy

- Keep runtime source-of-truth files in canonical project locations.
- Archive run-specific generated evidence under `improvements/history/...`
  unless the active item explicitly requires keeping it live.
- Prefer committing regeneration scripts/automation over committing large
  generated artifacts as permanent source-of-truth.

## Command Surface Note

- Canonical developer command surface is `python scripts/dev.py ...`.
- Harness/evaluation workflows are demoted under:
  - `python scripts/dev.py harness <workflow> ...`

## Compatibility Note

`CLAUDE.md` is retained as a compatibility shim for tools that auto-load that
filename. This `AGENTS.md` plus the harness docs are the authoritative workflow
source.
