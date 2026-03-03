# Remove stale run_true_tests command references from active docs

## Problem

Active repository docs still reference `python run_true_tests.py`, but
`run_true_tests.py` does not exist in repo root. This causes command-surface
drift and can block execution protocol validation when contributors follow
documented commands.

## Proposed Solution

1. Audit active documentation for references to `run_true_tests.py`.
2. Remove or replace stale references with commands that exist today
   (for example `python -m pytest -q` and targeted pytest paths).
3. Keep archival/historical documents untouched unless they are currently used
   as operational entrypoints.
4. Keep scope docs-only; no code or runtime behavior changes.

## Files Affected

- CLAUDE.md
- improvements/VISION.md
- improvements/minors/46-add-refactor-phase-test-gate-checklist.md
- improvements/HARNESS_BOOTSTRAP_CHECKLIST.md (if command references are expanded there)

## Acceptance Criteria

- [x] No active runtime/onboarding doc advertises `python run_true_tests.py` as a runnable command.
- [x] Replacement commands in active docs are executable with current repo tooling.
- [x] Any remaining references are clearly historical or archived context, not current workflow guidance.
