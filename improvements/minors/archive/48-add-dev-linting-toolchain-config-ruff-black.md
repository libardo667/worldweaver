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
- `README.md` (dev command usage notes)
- `improvements/HARNESS_BOOTSTRAP_CHECKLIST.md` (gate/command usage notes)
- `src/api/game/spatial.py`

## Assumptions

- This item is low risk and behavior-preserving; no API contract changes are intended.
- Initial lint rollout is scoped to minimal config and targeted hygiene, not repo-wide reformatting.
- Lint commands are documented and runnable in local dev environments with `ruff`/`black` installed.

## Validation Commands

- `python -m pytest -q`
- `npm --prefix client run build`
- `python -m ruff check src/api/game/state.py src/api/game/spatial.py`
- `python -m black --check src/api/game/state.py src/api/game/spatial.py`

## Risks & Rollback

- Risk: introducing stricter lint rules can surface unrelated legacy issues if expanded too quickly.
- Rollback: revert this item's commit to remove lint config and focused hygiene edits.

## Acceptance Criteria

- [x] No behavior changes are introduced by hygiene edits.
- [x] Touched modules use consistent logger declaration style.
- [x] `pyproject.toml` contains minimal, valid `ruff` and `black` configs.
- [x] No large formatting-only diff is introduced.
- [x] Existing tests still pass.
