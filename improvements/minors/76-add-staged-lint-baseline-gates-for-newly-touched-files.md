# Add staged lint baseline gates for newly touched files while major 50 remains in progress

## Problem

`improvements/ROADMAP.md` tracks repo-wide lint debt as non-blocking until major
`50` is complete. This protects momentum, but it still allows new lint debt to
enter changed files unless guarded in CI.

## Proposed Solution

Add a staged lint gate that enforces hygiene for changed files without requiring
full repo cleanup:

1. Add a CI check that runs `ruff`/`black --check` on Python files changed in
   the PR.
2. Keep `python scripts/dev.py lint --all` as non-blocking debt visibility.
3. Document this as an interim policy until major `50` closes.
4. Ensure local command parity so contributors can run the same changed-file
   check before pushing.

## Files Affected

- `scripts/dev.py`
- `.github/workflows/*`
- `README.md`
- `improvements/ROADMAP.md`

## Acceptance Criteria

- [ ] CI fails if changed Python files violate `ruff` or `black --check`.
- [ ] CI does not require full-repo green lint while major `50` is still open.
- [ ] `scripts/dev.py` exposes a local command equivalent for changed-file lint.
- [ ] Interim lint policy is documented in roadmap/readme command surfaces.

