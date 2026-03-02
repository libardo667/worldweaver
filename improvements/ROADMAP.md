# WorldWeaver Comprehensive Roadmap (Updated 2026-03-02)

This is the single execution roadmap for both:
- product capability milestones aligned to `VISION.md`, and
- internal refactor milestones that keep API behavior stable while improving maintainability.

## Current State

- Major 25 (`build-world-memory-graph-and-fact-layer`) is implemented.
- Next product major is `26-add-event-sourced-world-state-projection.md`.
- Refactor backlog is majors `32-37` and minors `45-49`.

## Non-Negotiable Guardrails

1. No route/path/payload shape changes unless explicitly approved.
2. Keep API layer thin (routing + validation only).
3. Consolidate duplicate logic into services (selection, normalization, persistence, ingest).
4. End each phase with green tests:
   - `pytest -q`
   - optional `python run_true_tests.py`

## Product Capability Track (Vision-Driven Majors)

1. `26-add-event-sourced-world-state-projection.md`
2. `27-ground-freeform-actions-in-world-facts.md`
3. `22-narrative-beats-as-semantic-field-lenses.md`
4. `23-seamless-dual-layer-navigation.md`
5. `24-real-time-contextual-storylet-adaptation.md`
6. `28-add-runtime-storylet-synthesis-for-sparse-context.md`
7. `29-add-player-goal-and-arc-tracking.md`
8. `30-build-api-first-web-client-v1.md`
9. `31-add-narrative-evaluation-harness.md`

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

1. `45-add-route-smoke-tests-for-api-surface.md`
2. `32-extract-storylet-normalization-and-location-helpers.md`
3. `33-move-storylet-selection-out-of-game-router.md`
4. `34-introduce-session-service-and-shared-cache-module.md`
5. `35-split-game-router-into-topic-subrouters.md`
6. `36-split-author-router-and-extract-ingest-pipeline.md`
7. `37-refactor-spatial-json-handling-with-centralized-helpers.md`
8. `26-add-event-sourced-world-state-projection.md`
9. `27-ground-freeform-actions-in-world-facts.md`
10. `22-narrative-beats-as-semantic-field-lenses.md`
11. `23-seamless-dual-layer-navigation.md`
12. `24-real-time-contextual-storylet-adaptation.md`
13. `28-add-runtime-storylet-synthesis-for-sparse-context.md`
14. `29-add-player-goal-and-arc-tracking.md`
15. `30-build-api-first-web-client-v1.md`
16. `31-add-narrative-evaluation-harness.md`
17. `48-add-dev-linting-toolchain-config-ruff-black.md`
18. `49-rename-fastapi-title-to-worldweaver-backend.md`
19. `46-add-refactor-phase-test-gate-checklist.md`

## Notes

- Use majors for multi-file/system-level work and minors for focused, low-risk tasks.
- Keep changes incremental and commit per cohesive step.
- Minors `33`, `35-36`, `38-44` remain valid tactical work that supports majors `26-31`.
