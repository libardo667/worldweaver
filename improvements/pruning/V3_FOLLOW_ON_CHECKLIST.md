# V3 Follow-On Checklist From Batch B Pruning

Date: `2026-03-06`
Status: `planning_only_additive`

## Purpose
- Capture v3-relevant follow-on opportunities discovered during Batch B pruning.
- Keep this as a handoff artifact for a separate v3-focused implementation chat.

## Scope Notes
- This checklist proposes additive follow-ons only.
- If a slice has no meaningful v3 linkage, it is marked explicitly.

## Runtime API Slices
| Slice | V3 Follow-On | Priority | Roadmap Alignment |
| --- | --- | --- | --- |
| `BATCH_B_RUNTIME_API_SLICE_1` | Extend shared runtime trace envelope with additive v3 context (`lane_source`, `projection_id`, `canon_commit_id`). | high | major `102`, major `103`, minor `102` |
| `BATCH_B_RUNTIME_API_SLICE_2` | Add optional prefetch budget metadata fields (`budget_ms`, `max_nodes`, `expansion_depth`) in helper-level diagnostics. | high | minor `104`, major `104` |
| `BATCH_B_RUNTIME_API_SLICE_3` | Extend orchestration adapters with projection seed refs and lane provenance pass-through (non-authoritative). | high | major `102`, major `103` |
| `BATCH_B_RUNTIME_API_SLICE_4` | Expand `RouteRuntimeContext` with additive v3 fields and stable logging keys for lane matrix comparisons. | medium | major `104`, minor `105` |

## Runtime Services Slices
| Slice | V3 Follow-On | Priority | Roadmap Alignment |
| --- | --- | --- | --- |
| `BATCH_B_RUNTIME_SERVICES_SLICE_1` | Introduce migration adapter mapping legacy smoothing/deepening toggles to v3 lane toggles (world/scene/player). | high | major `102`, minor `104` |
| `BATCH_B_RUNTIME_SERVICES_SLICE_2` | Emit structured skip-reason counters suitable for v3 harness metrics (`disabled`, `not_selected`, `budget_exhausted`). | medium | minor `102`, major `104` |
| `BATCH_B_RUNTIME_SERVICES_SLICE_3` | Once v3 lanes are active, retire legacy improver direct paths fully behind explicit rollout gates. | medium | major `102`, major `103` |

## Tests Integration Slices
| Slice | V3 Follow-On | Priority | Roadmap Alignment |
| --- | --- | --- | --- |
| `BATCH_B_TESTS_INTEGRATION_SLICE_1` | No strong v3-specific follow-on needed beyond existing hygiene gains. | none | n/a |
| `BATCH_B_TESTS_INTEGRATION_SLICE_2` | Add shared assertions for additive v3 response fields (`projection_id`, `clarity_level`, `lane_source`) when flags are enabled. | high | minor `103`, minor `102` |
| `BATCH_B_TESTS_INTEGRATION_SLICE_3` | Extend harness metric key sets for projection outcomes (`hit`, `waste`, `veto`) and lane latency splits. | high | minor `102`, major `104` |
| `BATCH_B_TESTS_INTEGRATION_SLICE_4` | Add reusable invalidation test helpers for commit-conflict projection branch pruning. | high | major `103` |
| `BATCH_B_TESTS_INTEGRATION_SLICE_5` | Add lane-matrix parameter bundles and budget sweep fixtures to new split modules. | medium | major `104` |
| `BATCH_B_TESTS_INTEGRATION_SLICE_6` | Add end-to-end lifecycle order tests (`ack -> commit -> narrate -> hint -> weave_ahead`) plus projection metadata propagation checks. | high | major `102`, minor `105` |

## Frontend Source Slices
| Slice | V3 Follow-On | Priority | Roadmap Alignment |
| --- | --- | --- | --- |
| `BATCH_B_FRONTEND_SOURCE_SLICE_1` | Add shared frontend v3 vocab types in `appHelpers` domain (`clarity_level`, lane IDs, projection-ref shape). | medium | minor `103`, major `102` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_2` | Add optional topbar status chips for lane activity and budget health (feature-flagged). | low | major `104` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_3` | Add dedicated `PlayerHintPanel` slot in Explore center-column for player narrator output lane. | high | major `102` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_4` | Group Explore props into typed v3-ready bundles (`sceneLane`, `hintLane`, `projectionContext`). | medium | major `102` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_5` | Ensure reset flows clear non-canon projection/hint frontend caches explicitly. | high | major `103` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_6` | Map UI phase helpers to v3 lifecycle labels and emit structured phase telemetry events. | medium | minor `102`, major `104` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_7` | Replace no-op narrator hooks with feature-flagged adapter implementation; keep default noop for safe rollback. | high | major `102`, minor `104`, minor `105` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_8` | Promote lane adapters from no-op to feature-flagged implementations and move lane-specific notice dictionaries to adapter-owned config. | high | major `102`, minor `104` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_9` | Feed `SceneLanePanel` and `PlayerHintPanel` from typed lane payload contracts and wire player-lane hint content from runtime metadata. | high | major `102`, minor `103` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_10` | Upgrade feature-flagged topbar chips from local heuristics to runtime-sourced lane/budget telemetry and retire generic fallback status copy under v3 flags. | medium | major `104`, minor `105` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_11` | Promote parsed v3 metadata (`projection_ref`, `clarity_level`, `lane_source`) into shared frontend runtime contracts and remove duplicated response-shape assumptions in view components. | high | minor `103`, minor `102` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_12` | Promote `useSessionLifecycle` cache invalidation hooks from coarse thread/world scope to explicit projection/session cache policy drivers, keyed by v3 commit lineage. | high | major `103`, major `102` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_13` | Use `ModeRouter` payload boundaries as the canonical lane-context ingress for mode-level UI and remove mixed mode/data assembly logic from `App.tsx`. | medium | major `102` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_14` | Elevate projection-scoped prefetch cache keys and optional budget metadata seams into canonical commit-lineage cache policy once v3 runtime emits authoritative projection/budget telemetry. | high | major `103`, major `104` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_15` | Keep mode payload assembly centralized in `useModeRouterPayload` and promote grouped lane-context schemas into shared v3 mode contracts before lane implementations become non-noop. | medium | major `102`, minor `103` |
| `BATCH_B_FRONTEND_SOURCE_SLICE_16` | Keep shared `ExploreModePayload` lane-contract normalization as the single mode-routing ingress and evolve it into the canonical v3 lane payload contract surface. | high | major `102`, minor `103`, minor `104` |

## Suggested Implementation Order (V3 Follow-On)
1. Add additive diagnostics/field assertions (`tests_integration` slices 2/3/6 + runtime_api slices 1/4).
2. Implement projection/commit safety mechanics (`tests_integration` slice 4 + runtime_services slice 2/3 + frontend slice 5).
3. Implement lane experience and UI surfaces (`frontend` slices 3/4/7 + topbar slice 2 optional polish).

## Upcoming Slice First-Thoughts (Live)

Use this section as a rolling pre-slice note area.

Process rule:
- Before each new pruning slice starts, add one row with first thoughts.
- After slice completion, move the validated outcome into the matching domain table above.
- Use decision tags consistently:
  - `Fit`: keep structure as a direct v3 boundary.
  - `Modify`: keep file/flow but reshape contract for v3 lane/projection model.
  - `Discard`: remove legacy behavior once v3 replacement lands behind flag gates.

| Planned Slice (Pruning Flow) | Likely Touched Code | First Thought (Fit / Modify / Discard) | V3 Link |
| --- | --- | --- | --- |
| `(Batch B closed)` | `n/a` | Batch B slice flow is complete through slice 16. Next pruning step is Batch C (`harness_source` demotion), with no strong direct v3 UI-contract follow-on. | n/a |
