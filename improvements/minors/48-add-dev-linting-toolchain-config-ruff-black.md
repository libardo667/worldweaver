# Add hygiene pass and dev linting toolchain configuration (ruff + black)

## Problem

As refactors move code across modules, unused imports and inconsistent logger patterns accumulate. The repository also lacks minimal, centralized lint/format configuration to keep hygiene consistent.

## Proposed Solution

1. Run a focused hygiene pass on touched modules:
   - remove unused imports/dead locals
   - standardize logger declarations to `logger = logging.getLogger(__name__)`
2. Add minimal `ruff` and `black` config in `pyproject.toml`.
3. Add lightweight usage notes to a dev-facing doc/checklist.
4. Do not mass-format the repo in this step; keep diffs focused.

## Files Affected

- `pyproject.toml`
- `improvements/refactor_phase_checklist.md` (or dev doc reference)
- `src/api/**/*.py`
- `src/services/**/*.py`
- `src/models/**/*.py` (if needed)

## Acceptance Criteria

- [ ] No behavior changes are introduced by hygiene edits.
- [ ] Touched modules use consistent logger declaration style.
- [ ] `pyproject.toml` contains minimal, valid `ruff` and `black` configs.
- [ ] No large formatting-only diff is introduced.
- [ ] Existing tests still pass.
