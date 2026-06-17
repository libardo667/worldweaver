# Relocate CI to the repo root and wire the public leak-sweep gate

## Problem

After the 5-repo → monorepo consolidation, the GitHub Actions workflows still live under
`worldweaver_engine/.github/workflows/` (`ci-gates.yml`, `narrative-eval-smoke.yml`). GitHub only runs
workflows from the **repository-root** `.github/workflows/`, and worldweaver has **no root `.github/`** — so
these workflows are effectively **dormant** at the monorepo level (the CI gates referenced in `CLAUDE.md`
are not actually triggering on push/PR).

Separately, the public-repo cleanup added `scripts/check-public.sh` (a tracked-tree leak-sweep — worldweaver
is published in place with no export scrub) which currently has no CI gate.

## Proposed Solution

- Create root `.github/workflows/` and move/relink the engine workflows so they trigger at the monorepo
  root (adjust `working-directory`/paths to `worldweaver_engine/` and `ww_agent/` as needed).
- Add a `public-hygiene` job/workflow that runs `scripts/check-public.sh` and fails the build on any leak.
- Confirm the relocated gates still match `CLAUDE.md`'s description (gate3-strict + pytest-warning-budget +
  narrative-eval-smoke).

## Files Affected

- `.github/workflows/*` (new, at repo root)
- `worldweaver_engine/.github/workflows/{ci-gates,narrative-eval-smoke}.yml` (move/retire)
- `scripts/check-public.sh` (wired as a gate)

## Acceptance Criteria

- [ ] Workflows live at repo-root `.github/workflows/` and actually trigger on push/PR.
- [ ] `scripts/check-public.sh` runs in CI and fails on any tracked personal-path/token leak.
- [ ] The gates described in `CLAUDE.md` (gate3-strict, pytest-warning-budget, narrative-eval-smoke) run from
      the new location.

## Risks & Rollback

- Path/`working-directory` mismatches can make a relocated workflow silently no-op. Verify with an actual PR
  run, not just YAML review.
- Rollback: delete the root `.github/` and restore the engine-local workflows (git).
