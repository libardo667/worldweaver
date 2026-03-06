# Batch B Frontend Source Slice 10

Date: `2026-03-06`
Status: `completed`

## Scope
- Continue `frontend_source` simplification by cleaning topbar runtime status plumbing.
- Introduce feature-flagged lane and budget chips while preserving current default topbar behavior.

## Changes
1. Refactored `client/src/app/appHelpers.ts`:
- added `ENABLE_TOPBAR_RUNTIME_STATUS_CHIPS` feature flag (`VITE_WW_ENABLE_TOPBAR_RUNTIME_STATUS_CHIPS`, default `false`).
- added typed topbar status model and builders:
  - `TopbarRuntimeStatusModel`
  - `buildTopbarRuntimeStatus(...)`
- centralized lane-state and budget-health derivation logic used by topbar rendering.

2. Refactored `client/src/App.tsx`:
- computes `topbarRuntimeStatus` via `useMemo(...)` from busy state, turn pending flags, onboarding state, and prefetch status.
- passes one runtime status object into topbar instead of wiring raw notice text directly.

3. Refactored `client/src/components/AppTopbar.tsx`:
- replaced direct backend-status text selection with `runtimeStatus.summaryText`.
- added optional runtime chips (scene/world/player lane + budget health) when feature flag is enabled.

4. Updated `client/src/styles.css`:
- added topbar runtime chip styles and tone variants (`active`, `ok`, `warn`, `off`).

## Guardrail Verification
Commands:
- `npm --prefix client run build`
- `python scripts/dev.py quality-strict`

Results:
- frontend build: pass
- strict gate: pass (`590 passed`)

## Batch B Impact
- Reduced topbar status drift by centralizing status derivation in one typed helper.
- Added an additive, feature-flagged v3-ready status surface without changing default UI behavior.
