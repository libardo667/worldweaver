# PRUNING Lane 1 Evidence (2026-03-03)

## Files Changed
- `client/src/App.tsx`
- `client/src/components/Compass.tsx`
- `client/src/components/PlacePanel.tsx`
- `client/src/hooks/useKeyboardNavigation.ts`
- `client/src/styles.css`

## Validations Run And Results
1. `npm --prefix client run build`
   - Result: pass
   - Notes: TypeScript compile and Vite production build completed successfully.

2. `python -m pytest -q tests/contract/test_spatial_navigation.py tests/contract/test_spatial_move.py`
   - Result: pass
   - Notes: `2 passed`; existing pydantic namespace warnings were emitted but no test failures.

## Unresolved Risks
- Lane 1 now treats compass directions as hints and allows any direction attempt. This intentionally shifts authority to the movement API; if backend traversability/direction metadata remains noisy, users may still see frequent blocked-move info toasts.
- Spatial refresh is no longer awaited in post-turn completion. Turn UX is improved, but compass direction freshness can lag briefly after a turn under high latency.
- No dedicated frontend automated tests cover compass affordance semantics or blocked-move toast behavior; regressions here are currently detected via build/contract test coverage and manual verification.

## Handoff Notes For Integration
- Contract dependencies observed:
  - `C1` spatial navigation payload shape remains consumed without required-field assumptions changed.
  - `C2` blocked-move backend detail string (`Cannot move in that direction`) is now explicitly handled as an info UX path.
  - `C3` prefetch API surface unchanged by Lane 1 edits.
- Integration expectation with Lane 2:
  - If Lane 2 improves traversability accuracy in `directions`, Lane 1 UI will automatically reflect higher confidence via highlighted compass buttons.
  - If Lane 2 changes blocked-move detail formatting while preserving semantics, keep the exact `detail` string stable or coordinate an additive signal to avoid degraded blocked-move UX classification.
- Scope boundary maintained: no backend or API contract file edits were made in this lane.
