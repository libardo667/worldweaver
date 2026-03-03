# WorldWeaver Comprehensive Roadmap (Updated 2026-03-03)

This is the single execution roadmap for both:
- product capability milestones aligned to `VISION.md`, and
- internal refactor milestones that keep API behavior stable while improving maintainability.

## Current State

- Core refactor track is complete through major `37` (API surface stabilized).
- Player-facing UI is live through Explore + Reflect + Constellation debug (major `30`, minors `50-54`, majors `38-39`).
- Constellation currently ships as a list/detail debug surface; graph rendering is tracked as follow-up minor `65`.
- Onboarding/world bootstrap critical path is aligned through major `45` (explicit session bootstrap + legacy seed decoupling).
- Next product majors are:
  - `40-add-create-mode-preferences-and-lenses.md`
  - `41-add-legends-export-and-run-artifacts.md`
  - `42-add-continuous-loading-frontier-prefetch.md`
- Primary experience risks are:
  - turn latency (continuous loading still in progress).
  - local runtime setup friction (multi-process startup and env drift).
  - compass/spatial reliability still affecting perceived turn quality.

## Non-Negotiable Guardrails

1. No route/path/payload shape changes unless explicitly approved.
2. Keep API layer thin (routing + validation only).
3. Consolidate duplicate logic into services (selection, normalization, persistence, ingest).
4. End each phase with green tests:
   - `python -m pytest -q`

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
11. `45-align-onboarding-bootstrap-with-world-generation.md`
12. `40-add-create-mode-preferences-and-lenses.md`
13. `41-add-legends-export-and-run-artifacts.md`
14. `42-add-continuous-loading-frontier-prefetch.md`
15. `43-add-progressive-turn-ux-and-world-weaving-prompts.md`
16. `44-split-freeform-action-into-intent-validate-narrate.md`
17. `45-centralize-prompt-and-model-management.md`

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
7. `46-operationalize-dev-runtime-with-compose-and-tasks.md`
8. `47-demote-compass-to-optional-assistive-navigation-layer.md`

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
- (UI minors) ~~51-compass-keyboard-navigation-ui.md~~
- (UI minors) ~~52-world-change-receipts-strip.md~~
- (UI minors) ~~53-memory-panel-search-and-pin.md~~
- (UI minors) ~~54-mobile-accessibility-pass.md~~
- ~~38-add-reflect-mode-chronicle-ui.md~~
- ~~39-add-semantic-constellation-debug-view.md~~

~~15. `45-align-onboarding-bootstrap-with-world-generation.md`~~
- (bootstrap minors) ~~61-add-bootstrap-provenance-and-reset-contract.md~~
- (bootstrap minors) ~~62-remove-production-default-seed-vars-and-test-storylets.md~~
- (bootstrap minors) ~~63-wire-client-onboarding-to-session-bootstrap.md~~
- (bootstrap minors) ~~64-add-critical-path-regression-tests-for-onboarding-bootstrap.md~~
~~16. `40-add-create-mode-preferences-and-lenses.md`~~
~~17. `41-add-legends-export-and-run-artifacts.md`~~
~~18. `55-add-latency-instrumentation-for-turns.md`~~
~~19. `42-add-continuous-loading-frontier-prefetch.md`~~
- ~~56-add-prefetch-endpoints-and-status.md~~
- ~~59-prefer-prefetched-frontier-in-selector.md~~
~~20. `43-add-progressive-turn-ux-and-world-weaving-prompts.md`~~
- ~~`57-add-client-prefetch-hook.md`~~
- ~~`58-add-progressive-loading-indicator.md`~~
- ~~`60-add-onboarding-world-weaving-prompts.md`~~
~~21. `44-split-freeform-action-into-intent-validate-narrate.md`~~
~~22. `45-centralize-prompt-and-model-management.md`~~
23. `31-add-narrative-evaluation-harness.md`
24. `48-add-dev-linting-toolchain-config-ruff-black.md`
25. `49-rename-fastapi-title-to-worldweaver-backend.md`
26. `46-add-refactor-phase-test-gate-checklist.md`
27. `65-add-constellation-graph-view-v1.md`
28. `66-compass-redaction-for-inaccessible-moves.md`
29. `46-operationalize-dev-runtime-with-compose-and-tasks.md`
- (operational minors) ~~`69-add-root-runtime-readme-and-harness-link.md`~~
- (operational minors) ~~`70-remove-stale-run-true-tests-command-references.md`~~
- (operational minors) ~~`67-add-dev-runtime-preflight-and-command-surface.md`~~
30. `47-demote-compass-to-optional-assistive-navigation-layer.md`
- (operational minors) `68-make-place-panel-refresh-best-effort-after-turn-render.md`

## UI/Client Minors (Low-risk UX increments)

~~19. `50-client-explore-layout-panels.md`~~
~~20. `51-compass-keyboard-navigation-ui.md`~~
~~21. `52-world-change-receipts-strip.md`~~
~~22. `53-memory-panel-search-and-pin.md`~~
~~23. `54-mobile-accessibility-pass.md`~~
24. `65-add-constellation-graph-view-v1.md`
25. `66-compass-redaction-for-inaccessible-moves.md`
26. `68-make-place-panel-refresh-best-effort-after-turn-render.md`

## Bootstrap Alignment Minors (Critical Path)

~~1. `61-add-bootstrap-provenance-and-reset-contract.md`~~
~~2. `62-remove-production-default-seed-vars-and-test-storylets.md`~~
~~3. `63-wire-client-onboarding-to-session-bootstrap.md`~~
~~4. `64-add-critical-path-regression-tests-for-onboarding-bootstrap.md`~~

## Latency & Continuous Loading Minors (Operational)

~~1. `55-add-latency-instrumentation-for-turns.md`~~
~~2. `56-add-prefetch-endpoints-and-status.md`~~
~~3. `57-add-client-prefetch-hook.md`~~
~~4. `58-add-progressive-loading-indicator.md`~~
~~5. `59-prefer-prefetched-frontier-in-selector.md`~~
~~6. `60-add-onboarding-world-weaving-prompts.md`~~

## Operational Runtime Minors (Developer Experience)

1. ~~`69-add-root-runtime-readme-and-harness-link.md`~~
2. ~~`70-remove-stale-run-true-tests-command-references.md`~~
3. ~~`67-add-dev-runtime-preflight-and-command-surface.md`~~

## Meta: Agentic Harness

- Reusable harness docs live in `improvements/harness/`.
- Start with `improvements/harness/README.md` and
  `improvements/harness/00-ADOPTION_GUIDE.md`.
- Use `improvements/harness/templates/` to bootstrap major/minor/task docs in
  new repositories.

## Notes

- Use majors for multi-file/system-level work and minors for focused, low-risk tasks.
- Keep changes incremental and commit per cohesive step.
- Minors should stay as standalone docs for follow-up work rather than inline roadmap notes.
