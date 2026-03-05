# Add staged lint baseline gates for newly touched files while major 50 remains in progress

## Disposition

Superseded by completed major `50-establish-full-project-lint-baseline-and-ci-gates.md`.

Reason:

- This minor proposed an interim changed-file lint policy only while full-repo
  lint remained non-blocking.
- Major `50` closed that gap with canonical-scope lint/format enforcement and
  CI-required Gate 3 checks.
- Follow-on hardening now continues under minor `96` (expanded static scope +
  warning budget), not this interim policy.

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
