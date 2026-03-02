# WorldWeaver Comprehensive Roadmap (Updated 2026-03-02)

This is the single execution roadmap for both:
- product capability milestones aligned to `VISION.md`, and
- internal refactor milestones that keep API behavior stable while improving maintainability.

## Current State

- Next product major is `27-ground-freeform-actions-in-world-facts.md`.
- Refactor backlog is majors `32-37` and minors `45-49`.

## Non-Negotiable Guardrails

1. No route/path/payload shape changes unless explicitly approved.
2. Keep API layer thin (routing + validation only).
3. Consolidate duplicate logic into services (selection, normalization, persistence, ingest).
4. End each phase with green tests:
   - `pytest -q`
   - optional `python run_true_tests.py`

## Product Capability Track (Vision-Driven Majors)

1. `27-ground-freeform-actions-in-world-facts.md`
2. `22-narrative-beats-as-semantic-field-lenses.md`
3. `23-seamless-dual-layer-navigation.md`
4. `24-real-time-contextual-storylet-adaptation.md`
5. `28-add-runtime-storylet-synthesis-for-sparse-context.md`
6. `29-add-player-goal-and-arc-tracking.md`
7. `30-build-api-first-web-client-v1.md`
8. `31-add-narrative-evaluation-harness.md`
9. `38-add-reflect-mode-chronicle-ui.md`
10. `39-add-semantic-constellation-debug-view.md`
11. `40-add-create-mode-preferences-and-lenses.md`
12. `41-add-legends-export-and-run-artifacts.md`



## Architecture Refactor Track (Behavior-Preserving)

Phase 0 and 7 minors:
1. `45-add-route-smoke-tests-for-api-surface.md`
2. `46-add-refactor-phase-test-gate-checklist.md`
3. `48-add-dev-linting-toolchain-config-ruff-black.md`
4. `49-rename-fastapi-title-to-worldweaver-backend.md`

Core refactor majors:
1. `32-extract-storylet-normalization-and-location-helpers.md`
2. `33-move-storylet-selection-out-of-game-router.md`
3. `34-introduce-session-service-and-shared-cache-module.md`
4. `35-split-game-router-into-topic-subrouters.md`
5. `36-split-author-router-and-extract-ingest-pipeline.md`
6. `37-refactor-spatial-json-handling-with-centralized-helpers.md`

## Integrated Execution Order (Recommended)

~~1. `45-add-route-smoke-tests-for-api-surface.md`~~
~~2. `32-extract-storylet-normalization-and-location-helpers.md`~~
~~3. `33-move-storylet-selection-out-of-game-router.md`~~
~~4. `34-introduce-session-service-and-shared-cache-module.md`~~
~~5. `35-split-game-router-into-topic-subrouters.md`~~
~~6. `36-split-author-router-and-extract-ingest-pipeline.md`~~
~~7. `37-refactor-spatial-json-handling-with-centralized-helpers.md`~~
~~8. `27-ground-freeform-actions-in-world-facts.md`~~
~~9. `22-narrative-beats-as-semantic-field-lenses.md`~~
~~10. `23-seamless-dual-layer-navigation.md`~~
~~11. `24-real-time-contextual-storylet-adaptation.md`~~
~~12. `28-add-runtime-storylet-synthesis-for-sparse-context.md`~~
~~13. `29-add-player-goal-and-arc-tracking.md`~~
~~14. `30-build-api-first-web-client-v1.md`~~
  - (UI minors) ~~50-client-explore-layout-panels.md~~
  - (UI minors) 51-compass-keyboard-navigation-ui.md
  - (UI minors) 52-world-change-receipts-strip.md
  - (UI minors) 53-memory-panel-search-and-pin.md
  - (UI minors) 54-mobile-accessibility-pass.md
  - 38-add-reflect-mode-chronicle-ui.md
  - 39-add-semantic-constellation-debug-view.md
  - 40-add-create-mode-preferences-and-lenses.md
  - 41-add-legends-export-and-run-artifacts.md
15. `31-add-narrative-evaluation-harness.md`
16. `48-add-dev-linting-toolchain-config-ruff-black.md`
17. `49-rename-fastapi-title-to-worldweaver-backend.md`
18. `46-add-refactor-phase-test-gate-checklist.md`
## UI/Client Minors (Low-risk UX increments)
~~19. `50-client-explore-layout-panels.md`~~
20. `51-compass-keyboard-navigation-ui.md`
21. `52-world-change-receipts-strip.md`
22. `53-memory-panel-search-and-pin.md`
23. `54-mobile-accessibility-pass.md`



## Notes

- Use majors for multi-file/system-level work and minors for focused, low-risk tasks.
- Keep changes incremental and commit per cohesive step.
- Minors `33`, `35-36`, `38-44` remain valid tactical work that supports majors `26-31`.
