# Relocate CI to the repo root and wire the public leak-sweep gate

## Update (2026-07-14) — implemented; awaiting first remote trigger

The monorepo gate now lives at `.github/workflows/ci-gates.yml`. It invokes the engine's canonical
`quality-strict` command, adds the previously missing agent suite, and runs `scripts/check-public.sh`
from the repository root. The dormant engine-local workflow was removed.

The original item also named `narrative-eval-smoke.yml`; Major 69 deleted that workflow because it
measured the deleted storylet/`/api/next` pipeline. It is intentionally **not** recreated. The current
CI contract is production code health: engine static/build/tests, agent tests, and public hygiene.

During local validation, the old warning-budget wrapper made a green 466-test suite fail because
dependency/Python warnings rose from a frozen count of 14 to 17. The keeper chose the lower-friction
solo-project contract: warnings remain visible in pytest output, but do not fail CI. The obsolete
`pytest-warning-budget` command and baseline artifact were removed; `quality-strict` now streams and
runs the complete suite directly.

Status: **verify** — local command validation is recorded below; the first push/PR after this change
must confirm GitHub schedules all three jobs from the root workflow.

### Local validation (2026-07-14)

- `python scripts/dev.py quality-strict` under Python 3.12: **466 passed**, client build and static
  checks green; warnings remain visible but non-blocking.
- `scripts/check-public.sh`: clean.
- `ww_agent/.venv/bin/python -m pytest tests -q`: **236 passed, 1 skipped, 1 failed** on the known
  Major 76 invariant (`src/runtime/source_gate.py` unmanifested). That failure is the next independent
  slice, not hidden or relaxed here.

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
- Confirm the relocated gates match `CLAUDE.md`'s current description (`quality-strict`, agent tests,
  public hygiene).

## Files Affected

- `.github/workflows/*` (new, at repo root)
- `worldweaver_engine/.github/workflows/{ci-gates,narrative-eval-smoke}.yml` (move/retire)
- `scripts/check-public.sh` (wired as a gate)

## Acceptance Criteria

- [~] The workflow lives at repo-root `.github/workflows/` with push/PR triggers; actual scheduling awaits
      the first remote push/PR.
- [x] `scripts/check-public.sh` is a root CI job and fails on tracked personal-path/token leaks.
- [x] `quality-strict` runs from `worldweaver_engine/`; the agent suite runs from `ww_agent/`.
      `narrative-eval-smoke` is retired with its deleted Major 69 pipeline.

## Risks & Rollback

- Path/`working-directory` mismatches can make a relocated workflow silently no-op. Verify with an actual PR
  run, not just YAML review.
- Rollback: delete the root `.github/` and restore the engine-local workflows (git).
