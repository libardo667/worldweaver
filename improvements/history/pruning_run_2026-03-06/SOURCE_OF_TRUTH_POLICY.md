# Source-Of-Truth Boundary Policy

Status: `proposed_locked_for_current_cycle`

## Core Principle
If a file is authored and defines product behavior, it is source-of-truth and remains in:
- `.../worldweaver/worldweaver`

If a file is generated/reproducible output, it is an artifact and should not be treated as source-of-truth.

## Decision Test (Per File)
1. If deleting the file changes runtime behavior and it cannot be recreated from code/config, classify as source-of-truth.
2. If deleting the file only removes output and it can be regenerated, classify as artifact.

## Storage Targets
- Source-of-truth:
  - Keep inside `.../worldweaver/worldweaver`.
- Relocatable artifacts:
  - Prefer parent workspace `.../worldweaver/` for bulky generated outputs.
- Local generated state kept in place:
  - Allowed when tooling conventions require in-place paths.

## Explicit Policy Decisions
- `client/node_modules/**`:
  - classification: generated dependency vendor state
  - source-of-truth: no
  - storage target: keep local/in-place (`worldweaver/worldweaver/client/node_modules`) for tool compatibility
- `client/dist/**`:
  - classification: generated build output
  - source-of-truth: no
  - storage target: local generated output (or external artifact store if desired)
- Playtest run artifacts (`playtests/sweeps/**`, `playtests/agent_runs/**`, `playtests/long_runs/**`, benchmark/playthrough markdowns):
  - classification: generated artifacts
  - source-of-truth: no
  - storage target: parent workspace artifact area preferred
- Logs/reports/local DB snapshots:
  - classification: generated/local artifacts
  - source-of-truth: no
  - storage target: parent workspace artifact area preferred

## In-Scope Source-Of-Truth Domains
- Runtime/backend code: `src/**`, `main.py`, migrations, runtime scripts.
- Test code defining expected behavior: `tests/**`.
- Frontend authored source/config: `client/src/**`, client config files.
- Harness/tooling source code used to execute eval workflows.
- Active planning docs that govern current execution.

## Non-Goals
- This policy does not itself move files.
- This policy does not mark any runtime code for deletion.
