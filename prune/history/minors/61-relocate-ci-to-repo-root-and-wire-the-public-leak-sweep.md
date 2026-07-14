# Relocate CI to the repo root and wire the public leak-sweep gate

> **Disposition: implementation complete; archived 2026-07-14.** The root workflow, engine check,
> agent suite, and public-hygiene job are present and locally validated. Observing GitHub schedule the next
> ordinary push is operational confirmation, not a reason to keep the migration item active.

## Update (2026-07-14) — implemented; awaiting first remote trigger

The monorepo gate now lives at `.github/workflows/ci-gates.yml`. It invokes the engine's canonical
`check` command, adds the previously missing agent suite, and runs `scripts/check-public.sh`
from the repository root. The dormant engine-local workflow was removed.

The original item also named `narrative-eval-smoke.yml`; Major 69 deleted that workflow because it
measured the deleted storylet/`/api/next` pipeline. It is intentionally **not** recreated. The current
CI contract is production code health: engine static/build/tests, agent tests, and public hygiene.

During local validation, the old warning-budget wrapper made a green 466-test suite fail because
dependency/Python warnings rose from a frozen count of 14 to 17. The keeper chose the lower-friction
solo-project contract: warnings remain visible in pytest output, but do not fail CI. The obsolete
`pytest-warning-budget` command and baseline artifact were removed; `check` now streams and
runs the complete suite directly.

The same principle applies to Python selection: CI follows the current Python 3 release instead of
pinning a minor version, while package metadata retains only the 3.11 syntax/tooling compatibility
floor. This is a single-maintainer health check, not a support matrix. The canonical command is named
`check` accordingly; passing it means the repository builds and tests without opting into a specially
named strict path.

Status: **verify** — local command validation is recorded below; the first push/PR after this change
must confirm GitHub schedules all three jobs from the root workflow.

### Local validation (2026-07-14)

- `python scripts/dev.py check` under Python 3.12: **466 passed**, client build and static
  checks green; warnings remain visible but non-blocking.
- `scripts/check-public.sh`: clean.
- `ww_agent/.venv/bin/python -m pytest tests -q`: **237 passed, 1 skipped** after the independent
  Major 76 manifest-classification repair.

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
- Confirm the relocated gates match `CLAUDE.md`'s current description (`check`, agent tests,
  public hygiene).

## Files Affected

- `.github/workflows/*` (new, at repo root)
- `worldweaver_engine/.github/workflows/{ci-gates,narrative-eval-smoke}.yml` (move/retire)
- `scripts/check-public.sh` (wired as a gate)

## Acceptance Criteria

- [~] The workflow lives at repo-root `.github/workflows/` with push/PR triggers; actual scheduling awaits
      the first remote push/PR.
- [x] `scripts/check-public.sh` is a root CI job and fails on tracked personal-path/token leaks.
- [x] `check` runs from `worldweaver_engine/`; the agent suite runs from `ww_agent/`.
      `narrative-eval-smoke` is retired with its deleted Major 69 pipeline.

## Risks & Rollback

- Path/`working-directory` mismatches can make a relocated workflow silently no-op. Verify with an actual PR
  run, not just YAML review.
- Rollback: delete the root `.github/` and restore the engine-local workflows (git).
