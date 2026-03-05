# Expand static quality gates to tests/scripts and add a pytest warning budget

## Problem

Major `50` established a green lint baseline and CI enforcement for the
canonical backend scope (`src/api`, `src/services`, `src/models`, `main.py`).
However, two quality gaps remain:

1. `tests/` and `scripts/` are not part of required lint gates.
2. `pytest` warnings are visible but not budgeted/enforced, allowing warning
   regressions over time.

## Scope Boundaries

- In scope: dev command surface, CI gate wiring, lint baseline cleanup for
  `tests/` and `scripts/`, warning budget artifact, and contributor docs.
- Out of scope: API contract changes or runtime behavior changes unrelated to
  static/test quality gates.

## Assumptions

- Existing pytest warning count baseline is accepted short-term and should be
  prevented from regressing.
- Extended lint scope should be enforced in CI only after formatting/lint drift
  in `tests/` and `scripts/` is cleared.

## Proposed Solution

Introduce a focused static-quality v2 hardening slice:

1. Expand lint coverage to include `tests/` and `scripts/` with a canonical
   command in `scripts/dev.py` (for example `lint-extended`).
2. Add a strict Gate 3 companion command (for example `gate3-strict`) that runs
   extended lint plus existing static/build checks.
3. Add CI enforcement for the strict gate once green.
4. Establish a pytest warning budget policy:
   - capture current warning baseline in an artifact,
   - fail CI on warning count regression above budget,
   - optionally burn down known warning classes in bounded follow-up slices.
5. Update README and harness docs so contributors use one stable strict command
   path locally and in CI.

## Files Affected

- `scripts/dev.py`
- `.github/workflows/ci-gates.yml`
- `README.md`
- `improvements/harness/04-QUALITY_GATES.md` (if gate wording needs alignment)
- `improvements/ROADMAP.md`
- `improvements/pytest-warning-baseline.json`

## Validation Commands

- `python -m ruff check src/api src/services src/models tests scripts main.py`
- `python -m black --check src/api src/services src/models tests scripts main.py`
- `python scripts/dev.py lint-extended`
- `python scripts/dev.py gate3-strict`
- `python scripts/dev.py pytest-warning-budget`
- `python scripts/dev.py quality-strict`
- `python -m pytest -q`
- `npm --prefix client run build`

## Acceptance Criteria

- [x] `python -m ruff check src/api src/services src/models tests scripts main.py` passes.
- [x] `python -m black --check src/api src/services src/models tests scripts main.py` passes.
- [x] `scripts/dev.py` exposes an extended lint/static command path and docs
      reference it as the strict quality path.
- [x] CI enforces the extended lint scope (not local-only).
- [x] A pytest warning budget artifact exists and CI fails on warning-count
      regression above the agreed threshold.
- [x] `python -m pytest -q` and `npm --prefix client run build` continue to pass.
- [x] No API route/path/payload contract changes are introduced.

## Risks & Rollback

- Risk: strict lint expansion introduces broad formatting churn in `tests/` and
  `scripts/`, increasing merge conflict probability for active branches.
- Rollback: revert this minor's dev/CI/doc updates and the extended-scope lint
  cleanup commit set.
- Safe-disable path: switch CI back to `python scripts/dev.py lint-all` and
  `python -m pytest -q` while keeping warning baseline artifact for reference.
