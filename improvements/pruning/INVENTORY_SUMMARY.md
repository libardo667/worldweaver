# Inventory Summary (Initial Census)

## Snapshot
- Total files in repository tree (including `.git`): `6796`
- Total assessable files in inventory (excluding `.git` internals): `3732`
- Source: recursive file census across repository root

## Counts By Category
- `frontend`: 2589
- `playtest_artifacts`: 463
- `planning_docs`: 238
- `tests`: 177
- `runtime`: 122
- `misc`: 38
- `reports`: 29
- `cache`: 26
- `migrations`: 18
- `tooling`: 16
- `harness`: 13
- `data`: 3

## Top-Level Hotspots
- `client`: 2589
- `playtests`: 463
- `improvements`: 238
- `tests`: 177
- `src`: 122

## Early Signals (Non-Final)
- The repository contains substantial local/dependency weight under `client/` (including `node_modules` binaries).
- `playtests/` contains many run artifacts that are likely high-volume, low-runtime-value for core backend operation.
- Runtime backend surface (`src/`) is comparatively small, making code-block-level pruning feasible after inventory triage.
- There are cache and local log residue files in repo root and tooling caches that should likely be formalized as generated/ignored artifacts.

## Next Step
Stage 2 and Stage 3 artifacts are now in place (`CRITICAL_PATH_MAP.md`, `BASELINE_FREEZE.md`).
Source-of-truth policy and bucketed inventory pass are now in place (`SOURCE_OF_TRUTH_POLICY.md`, `BUCKET_SUMMARY.csv`).
Next step is criteria sign-off using `SCORING_WORKSHEET.csv` before broad candidate scoring.
