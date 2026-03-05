# Expand static quality gates to tests/scripts and add a pytest warning budget

## Problem

Major `50` established a green lint baseline and CI enforcement for the
canonical backend scope (`src/api`, `src/services`, `src/models`, `main.py`).
However, two quality gaps remain:

1. `tests/` and `scripts/` are not part of required lint gates.
2. `pytest` warnings are visible but not budgeted/enforced, allowing warning
   regressions over time.

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
- `improvements/*warning-baseline*.md` (new artifact name TBD)

## Acceptance Criteria

- [ ] `python -m ruff check src/api src/services src/models tests scripts main.py` passes.
- [ ] `python -m black --check src/api src/services src/models tests scripts main.py` passes.
- [ ] `scripts/dev.py` exposes an extended lint/static command path and docs
      reference it as the strict quality path.
- [ ] CI enforces the extended lint scope (not local-only).
- [ ] A pytest warning budget artifact exists and CI fails on warning-count
      regression above the agreed threshold.
- [ ] `python -m pytest -q` and `npm --prefix client run build` continue to pass.
- [ ] No API route/path/payload contract changes are introduced.
