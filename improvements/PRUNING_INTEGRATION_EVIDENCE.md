# PRUNING Integration Evidence (2026-03-03)

## Change Summary
- Item ID(s): Pruning cycle from `improvements/PRUNING_COORDINATION_PLAN.md` (candidates 1-8 across lanes 1-4).
- PR Scope: Integrated lane outputs in planned order, resolved cross-lane conflicts with contract-first priority, and ran lane + final validation gates.
- Risk Level: High (multi-lane integration touching runtime, API compatibility, client UX, and toolchain docs/commands).

## Integration Order Executed
1. Lane 2 validation gate (backend spatial/prefetch contract baseline).
2. Lane 3 validation gate (legacy/runtime pruning + compatibility reduction).
3. Lane 1 validation gate (client navigation demotion/isolation).
4. Lane 4 validation gate (tooling/static debt visibility + verify wrapper).
5. Final full integration gates.

## Merge/Conflict Decisions
### Conflict A: Compass interaction model (Lane 1) vs traversability contract intent (Lane 2)
- Priority evaluation:
  - Contract stability: both approaches preserved API shape.
  - Correctness: traversable-only actions better match Lane 2 contract/testing intent and reduces blocked movement noise.
  - Simplicity: one authoritative source (`directions`) for actionable moves.
- Winning approach:
  - Keep Lane 2 traversability semantics authoritative in client controls.
  - Preserve Lane 1 non-blocking post-turn refresh improvements.
- Rejected approach:
  - Lane 1 "attempt-any-direction" controls (click + keyboard) because it reintroduced avoidable blocked movement attempts and weakened reliability goals.
- Concrete merge edits required:
  - `client/src/components/Compass.tsx`:
    - restored `availableDirections` filtering for keyboard hook input.
    - restored disabled state for non-traversable directions.
  - `client/src/hooks/useKeyboardNavigation.ts`:
    - restored `availableDirections` gating for movement hotkeys.
  - `client/src/components/PlacePanel.tsx`:
    - updated helper copy to reflect non-traversable routes as blocked.

### Conflict B: Lane 3 compatibility deletion vs existing debug/error-envelope contract tests
- Priority evaluation:
  - Contract stability: current test contract patches `src.api.author.SessionVars` and `src.api.author.Storylet`.
  - Correctness: removing those symbols caused a failing contract test and broke `scripts/dev.py verify`.
  - Simplicity: minimal re-export is smaller than reintroducing broad legacy alias surface.
- Winning approach:
  - Restore only minimal package exports required by existing contract usage.
- Rejected approach:
  - Full removal of package-level model symbols from `src.api.author`.
- Concrete merge edits required:
  - `src/api/author/__init__.py`:
    - re-export `SessionVars` and `Storylet` from `src.models`.
    - keep broader refactor-transition helper re-exports removed.

## Contract and Compatibility Outcome
- C1/C2/C3 preserved:
  - Spatial navigation and movement payload shapes unchanged.
  - `403` blocked movement detail remains `Cannot move in that direction`.
  - Prefetch endpoint/status payload shapes unchanged.
- C4 preserved:
  - `/api/reset-session` response envelope unchanged (`success`, `message`, `deleted`, `storylets_seeded`, `legacy_seed_mode`).
  - Legacy seed activation semantics remain tightened (explicit param + flag).
- C5 preserved:
  - `postprocess_new_storylets()` response envelope unchanged.
- C6 preserved:
  - No `/api/action/stream` event contract changes.

## Validations and Results
Lane 2 required gate:
- `python -m pytest -q tests/contract/test_spatial_navigation.py tests/contract/test_spatial_move.py tests/contract/test_spatial_map.py tests/service/test_spatial_navigator.py tests/api/test_prefetch_endpoints.py tests/service/test_prefetch_service.py tests/integration/test_spatial_navigation_integration.py`
- Result: PASS (`16 passed, 3 warnings`)

Lane 3 required gate:
- `python -m pytest -q tests/service/test_storylet_ingest.py tests/service/test_decomposed_functions.py tests/service/test_seed_data.py tests/api/test_game_endpoints.py tests/api/test_author_generate_world_confirmation.py tests/api/test_route_smoke.py`
- Result: PASS (`79 passed, 9 warnings`)

Lane 1 required gate:
- `npm --prefix client run build`
- Result: PASS
- `python -m pytest -q tests/contract/test_spatial_navigation.py tests/contract/test_spatial_move.py`
- Result: PASS (`3 passed, 3 warnings`)

Lane 4 required gate:
- `python -m ruff check src/api src/services src/models main.py`
- Result: FAIL (`121` violations; repository lint debt remains)
- `python -m black --check src/api src/services src/models main.py`
- Result: FAIL (`27 files would be reformatted`)
- `python scripts/dev.py verify`
- Result: PASS after integration fixes (`472 passed`, client build pass, compileall pass)

Final integration gate:
- `python -m pytest -q`
- Result: PASS (`472 passed, 11 warnings`)
- `npm --prefix client run build`
- Result: PASS

## Regressions Found and Fixed
1. Regression:
   - `tests/contract/test_error_envelopes.py::test_debug_endpoint_error_returns_500` failed with:
   - `AttributeError: module 'src.api.author' has no attribute 'SessionVars'`
   - Cause: Lane 3 removed package-level model exports used by existing patch contract.
   - Fix: restored minimal `SessionVars` and `Storylet` exports in `src/api/author/__init__.py`.

2. Regression risk:
   - Lane 1 introduced actionable attempts for non-traversable directions.
   - Cause: keyboard/click filtering no longer used `availableDirections`.
   - Fix: restored traversability-gated interactions while retaining non-blocking post-turn refresh.

## Follow-up Items Needed
1. Minor: decouple `/author/debug` test patch target from package-level model re-exports.
   - Goal: remove `src.api.author` symbol-export coupling and avoid lint-only imports in package init.
2. Major/minor continuation: full-project lint debt burn-down under `50-establish-full-project-lint-baseline-and-ci-gates`.
   - Goal: make `ruff`/`black` repo-scope gates green and enforceable.
3. Minor: add focused client tests for compass traversability affordance/keyboard parity.
   - Goal: prevent reintroduction of blocked-direction regressions in client behavior.
