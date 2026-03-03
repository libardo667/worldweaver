# Establish full-project lint baseline and CI enforcement gates

## Problem

Minor `48` introduced minimal `ruff`/`black` configuration and focused hygiene on
touched modules, but full-project linting is still red across many files in
`src/api`, `src/services`, and `src/models`. As a result, Gate 3 (build/static
health) cannot be enforced consistently at repository scope, and contributors
must rely on ad hoc per-file lint checks.

This leaves two operational gaps:

1. no reliable full-project static hygiene baseline, and
2. no CI-required lint gate for merge safety.

## Proposed Solution

Execute a behavior-preserving lint hardening major in phased steps:

1. Establish a full lint baseline:
   - run `ruff check` at project scope,
   - classify violations into safe auto-fixes vs manual edits,
   - track remaining buckets in a single lint-baseline artifact.
2. Reduce lint debt to green at project scope:
   - apply safe `ruff --fix` changes where behavior-preserving,
   - perform bounded manual edits for remaining errors,
   - avoid broad semantic refactors unrelated to lint findings.
3. Standardize command surface:
   - add canonical lint command(s) to `scripts/dev.py`,
   - update root and harness docs so Gate 3 uses one stable command path.
4. Enforce in CI:
   - add required lint/format checks to CI workflow(s),
   - fail merges when project-scope lint/format checks fail.
5. Preserve runtime safety:
   - run full regression validation (`pytest`, client build) after each lint batch.

## Files Affected

- `src/api/**/*.py`
- `src/services/**/*.py`
- `src/models/**/*.py`
- `main.py`
- `pyproject.toml`
- `scripts/dev.py`
- `.github/workflows/*` (if CI workflow is present; otherwise add one)
- `README.md`
- `improvements/HARNESS_BOOTSTRAP_CHECKLIST.md`
- `improvements/refactor_phase_checklist.md` (or equivalent gate checklist doc)
- `improvements/ROADMAP.md`

## Acceptance Criteria

- [ ] `python -m ruff check src/api src/services src/models main.py` passes with zero violations.
- [ ] `python -m black --check src/api src/services src/models main.py` passes.
- [ ] Canonical lint command(s) exist in `scripts/dev.py` and are documented in root/harness command surfaces.
- [ ] CI enforces lint/format as required Gate 3 checks (not optional/manual-only).
- [ ] `python -m pytest -q` passes after lint remediation.
- [ ] `npm --prefix client run build` passes after lint remediation.
- [ ] No route/path/payload contract changes are introduced by lint cleanup.

## Risks & Rollback

Large-scale lint edits can introduce accidental behavioral regressions,
especially in complex service modules with mixed responsibilities.

Rollback approach:

1. Keep changes batched and reversible by module group.
2. Revert the major's commits if regressions appear after lint cleanup.
3. Temporarily fall back to incremental lint-on-touched-files policy while
   preserving baseline tracking artifacts for re-entry.
