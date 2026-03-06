# Batch C Harness Source Slice 1

Date: `2026-03-06`
Status: `completed`

## Scope
- Demote harness/evaluation workflows out of the default dev command path while preserving compatibility for existing operator habits.

## Changes
1. Introduced demoted harness namespace in `scripts/dev.py`:
- added `harness` subcommand: `python scripts/dev.py harness <workflow> ...`
- centralized supported harness workflows via `HARNESS_COMMANDS`.

2. Kept legacy top-level aliases for compatibility:
- legacy commands (`eval`, `eval-smoke`, `sweep`, `llm-playtest`, `benchmark-three-layer`) now emit a warning directing users to the demoted namespace.
- restored raw argv pass-through for legacy aliases so option-like tokens continue working without `--` (for example, `python scripts/dev.py sweep --phase both ...`).

3. Updated operator-facing docs to use demoted path by default:
- `README.md`: task-surface harness commands now use `python scripts/dev.py harness ...`; harness commands removed from baseline validation command block.
- `playtest_harness/LLM_PLAYTEST_GUIDE.md`: primary and example invocations now use `python scripts/dev.py harness llm-playtest ...`.

## Guardrail Verification
Commands:
- `python scripts/dev.py harness sweep --dry-run --phase both --phase-a-configs 2 --phase-a-turns 2 --phase-b-turns 2 --phase-b-runs-per-config 1 --phase-b-top-k 1 --out-dir playtests/agent_runs`
- `python scripts/dev.py sweep --dry-run --phase both --phase-a-configs 2 --phase-a-turns 2 --phase-b-turns 2 --phase-b-runs-per-config 1 --phase-b-top-k 1 --out-dir playtests/agent_runs`
- `python scripts/dev.py eval --help`
- `python scripts/dev.py harness benchmark-three-layer --help`
- `python scripts/dev.py quality-strict`

Results:
- harness namespace command path: pass
- legacy alias command path: pass (with explicit warning)
- strict gate: pass (`590 passed`; warning budget unchanged)

## Batch C Impact
- Harness/eval workflows remain available but are no longer framed as part of the primary runtime/test command path.
- Default docs now steer operators toward production-critical validation commands, reducing accidental coupling to optional harness tooling.
