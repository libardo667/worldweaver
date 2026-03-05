# PR Evidence: Minor 96 - Expand Static Quality Gates to Tests/Scripts and Add Pytest Warning Budget

## Item

`improvements/minors/archive/96-expand-static-quality-gates-to-tests-scripts-and-warning-budget.md`

## Scope

Implemented strict static-quality v2 hardening by expanding lint scope to `tests/` and `scripts/`, adding strict dev/CI command paths, and enforcing a pytest warning budget from a committed baseline artifact.

## What Changed

| File | Change |
|------|--------|
| `scripts/dev.py` | Added strict command surface: `lint-extended`, `gate3-strict`, `pytest-warning-budget`, and `quality-strict`; added warning-budget parser/enforcement logic and extended lint scope constant. |
| `.github/workflows/ci-gates.yml` | Replaced lint-only gate job with strict Gate 3 enforcement (`python scripts/dev.py gate3-strict`) and switched backend test job to warning-budget enforcement (`python scripts/dev.py pytest-warning-budget`). |
| `README.md` | Documented strict local/CI command path and new warning-budget command. |
| `improvements/harness/04-QUALITY_GATES.md` | Aligned gate wording to include pytest warning budget and documented `python scripts/dev.py quality-strict` as strict path. |
| `improvements/ROADMAP.md` | Marked minor `96` complete and removed it from pending queue. |
| `improvements/pytest-warning-baseline.json` | Added warning budget artifact (`baseline_warning_count=14`, `max_allowed_increase=0`). |
| `tests/*`, `scripts/*` (format/lint cleanup) | Applied required lint/format baseline cleanup so extended scope is green under ruff + black. |

## Why This Matters

- It closes a real quality blind spot: `tests/` and `scripts/` now have the same enforced hygiene as core backend modules.
- It prevents warning regressions from silently accumulating by turning warning count into a tracked, enforceable budget.
- It gives one reproducible strict path for local and CI use, reducing "works locally but fails in CI" drift.
- It hardens comparative-playtest readiness by making the engineering baseline stable and auditable before experiment cycles.

## Acceptance Criteria Check

- [x] `python -m ruff check src/api src/services src/models tests scripts main.py` passes.
- [x] `python -m black --check src/api src/services src/models tests scripts main.py` passes.
- [x] `scripts/dev.py` exposes extended lint/static command path and docs reference it.
- [x] CI enforces extended lint scope via strict gate job.
- [x] Warning budget artifact exists and CI warning-budget command fails on regression.
- [x] `python -m pytest -q` and `npm --prefix client run build` pass.
- [x] No API route/path/payload contract changes were introduced.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No API contract changes (routes, payloads, envelopes unchanged).

### Gate 2: Correctness

- `python scripts/dev.py pytest-warning-budget` -> pass (`548 passed, 14 warnings`; budget allowed `14`)
- `python scripts/dev.py quality-strict` -> pass (includes pytest warning-budget pass)

### Gate 3: Build and Static Health

- `python -m ruff check src/api src/services src/models tests scripts main.py` -> pass
- `python -m black --check src/api src/services src/models tests scripts main.py` -> pass
- `python scripts/dev.py lint-extended` -> pass
- `python scripts/dev.py gate3-strict` -> pass
- `npm --prefix client run build` -> pass

## Operational Safety / Rollback

- Rollback path: revert this minor's `scripts/dev.py`, CI workflow, docs, warning baseline artifact, and lint-format cleanup changes.
- Safe-disable path: switch CI command back to `python scripts/dev.py lint-all` and `python -m pytest -q` while preserving the warning baseline artifact for future re-enable.
- Data/migration impact: none.

## Residual Risk

- Expanded lint scope introduced broad formatting churn in `tests/` and `scripts/`, which can increase short-term merge conflict frequency on active branches.
