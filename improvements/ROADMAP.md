# Roadmap

## Current State

**V3 is complete and operational.** V4 planning is underway.

- Product status: Scene-card JIT narration, motif instrumentation, sweep harnesses, non-canon projection BFS expansion, canon-safe commit/invalidation enforcement, projection-seeded narration/hint diagnostics, additive turn fallback/clarity diagnostics, projection/clarity harness metrics, structured world-fact channel, adaptive projection pruning with pressure telemetry, v3 smoke/soak gates, lane-matrix sweep operationalization, and bootstrap critical-path diagnostics are all operational. State manager is modularized into typed domain components.
- Architecture status: 3-layer model lanes with per-lane temperature axes, reducer authority enforced, projection runtime budgets/flags with adaptive pruning tiers, commit-boundary invalidation enforced, projection-seeded adaptation context wired, six-component composite score (latency + motif + failure + projection + clarity + narrator), AdvancedStateManager decomposed into 4 typed domains, schema-first world-fact extraction, `bootstrap_diagnostics` in every session bootstrap/start response, v3 smoke + soak gates green (807 tests, quality-strict clean).
- V3.5 patch status: JIT beat persistence, batch generation resilience, action pipeline unification, and storylet pool growth mechanisms are in progress (see V3.5 section below).

## Guardrails

1. No route/path contract breaks without explicit approval; new diagnostics must be additive.
2. Reducer remains the only canonical world-state mutation authority.
3. Projection data is always non-canon until commit and must be invalidated after conflicting commits.
4. Every major/minor item must include executable validation commands and PR evidence.
5. v3/v4 work must be feature-flagged with safe defaults and rollback paths.
6. V4 shared-world features must preserve v3 single-player functionality.

---

## V3.5: Stabilization and Pool Growth (In Progress)

Bridging work between v3 (complete) and v4 (planned). Focused on making the
existing single-player experience more dynamic and fixing pipeline gaps
discovered during agent-driven playtests.

### Completed (V3.5)

- `break` to `continue` in batch storylet generation — remaining batches survive individual failures.
- `ActionChoice` schema — added `intent` field so intent is not silently dropped from action responses.
- Unified action pipeline — freeform and choice inputs both route through `/action` with `choice_vars`/`choice_intent`.
- Location constraint in referee prompt — storylets use world bible location names.
- Starting storylet anchored to entry location.
- Connected graph constraint — referee prompt requires return paths to entry location.
- Double world-bible generation eliminated — single bible passed through bootstrap pipeline.
- JIT gate relaxed from `eligible == 0` to `eligible < threshold` (default 3).
- JIT beat persistence — beats saved as `source="jit_beat"` Storylet records with configurable TTL.
- Runtime synthesis budget raised — `max_per_session` 3 to 12, `min_eligible_storylets` 1 to 3.

### Known Gaps (V3.5)

- Freeform choices never include location transitions — Stage C generates choices with `set: {}`. Storylet-authored choices have location deltas; freeform-generated ones don't.
- `intent` field consistently null in choices — Stage B narrator not populating it.
- JIT beat fallback on all choice turns — `generate_next_beat` returning `_fallback_beat` (exception caught); haiku-4.5 fails JSON/choice validation with sparse frontier context.
- Spatial hint leaks raw action text into narration — `SpatialNavigator` appends `"Traces of {player_action_text} seem strongest to the North."` to narrative prose. `semantic_goal` must be distilled before hint generation, or hint injection disabled when goal text is not a short phrase.

---

## V3.5 Major: Unified Turn Pipeline

**Root cause**: `/action` and `/next` are parallel 500-line pipelines that never
share narration, JIT generation, or pool growth. JIT persistence only fires
from `/next`; the `/action` staged pipeline bypasses storylets entirely.
`active_storylets_count: 0` on every action turn.

**Goal**: One `process_turn` method. Freeform text and choice buttons enter
the same spine. Every turn can fire JIT, select storylets, and grow the pool.

Feature flag: `WW_ENABLE_UNIFIED_TURN_PIPELINE` (default `True`).

### Phase 0: Extract Shared Helpers (no behavior change) ✅

Inlined into `process_turn` — the 10-phase spine is self-contained, so standalone
helper extraction was not needed to keep the method readable.

### Phase 1: Unified Turn Input Contract ✅

- [x] `UnifiedTurnInput` dataclass — normalizes both `ActionRequest` and `NextReq`
- [x] `from_action_request()` and `from_next_request()` factory classmethods

### Phase 2: Implement `process_turn` — The Unified Spine ✅

Implemented with 9 phases (phases 7+8 merged for clarity):

```
1. IDEMPOTENCY CHECK (action only — hard early-return)
2. LOAD STATE + commit inbound vars/choice
3. SCENE CARD + SHARED CONTEXT
4. INTENT EXTRACTION (freeform only — Stage A; choice buttons skip)
5. STATE COMMIT (freeform: FreeformActionCommittedIntent + SystemTickIntent)
6. NARRATION SOURCE SELECTION:
   - is_freeform=True  → Stage C (render_validated_action_narration)
   - is_freeform=False → JIT (generate_next_beat + persist) or storylet path
7. POST-NARRATION BOOKKEEPING (arc, motifs, hints, fire effects, world events)
8. RESPONSE ASSEMBLY (diagnostics, vars, projection invalidation)
9. PERSIST (save_state, idempotent response)
```

Key behavior change: choice buttons (`is_freeform=False`) now route through
JIT/storylet narration instead of Stage A→C, enabling pool growth on every turn.

- [x] `process_turn` implemented on `TurnOrchestrator`
- [x] All existing API tests green (93 tests in action + game endpoint suites)

### Phase 3: Wire Old Methods as Thin Wrappers ✅

- [x] `process_action_turn`: delegates to `process_turn` when flag on; projects via `_as_action_response`
- [x] `process_next_turn`: delegates to `process_turn` when flag on; projects via `_as_next_response`
- [x] `_as_action_response` / `_as_next_response` projection helpers on `TurnOrchestrator`

### Phase 4: Update `/turn` Endpoint

- [ ] `run_unified_turn_orchestration` adapter in `orchestration_adapters.py`
- [ ] `/turn` endpoint calls unified pipeline directly
- [ ] Enable `enable_turn_endpoint` + `enable_unified_turn_pipeline` together

### Phase 5: Output Shape Unification (deferrable)

- [ ] `UnifiedTurnResponse` Pydantic model (superset of `ActionResponse` + `NextResp`)
- [ ] `/turn` returns unified shape; `/action` and `/next` project into legacy shapes
- [ ] Contract tests for all three response shapes

### Risk Mitigations

| Risk | Mitigation |
|------|------------|
| JIT early-return breaks phase sequence | JIT is a narration strategy in Phase 6, not an early-return; phases 7-9 always run |
| Simulation tick ordering differs | Unified: always runs after Phase 6 narration (all mutations visible) |
| Response shape mismatch | Phase 3 wrappers project into expected shape; unified shape is internal |
| Storylet fire effects (next only) | Phase 6 storylet branch runs them; freeform branch skips — clean conditional |

### Rollback

Set `WW_ENABLE_UNIFIED_TURN_PIPELINE=false`. Both legacy methods contain the full
original code below the flag check — no behavior change when flag is off.

---

## V3.5 → V4 Pruning Wave

Before V4 milestone work begins, prune V3 subsystems with high complexity and
low V4 leverage. See `improvements/VISION.md` for full rationale.

| Target | Strategy | Priority |
|---|---|---|
| BFS projection / adaptive pruning tiers | Prune | High — blocks V4 narrator shift |
| `SpatialNavigator` | Prune | High — actively broken (hint leak bug) |
| Storylet system (primary path) | Demote to legacy/fallback | Medium |
| Session bootstrap pipeline | Prune in V4 path | Medium |
| Motif governance (blocking sync) | Demote to async/best-effort | Low |

Pruning protocol per `improvements/harness/07-PRUNING_PLAYBOOK.md`:
freeze baseline tests → bounded commits → validate critical flows.

---

## V4: The Persistent Shared World

See `improvements/VISION.md` for full design rationale.

### V4 Milestones

#### M1: Shared World State

Shift from session-scoped to world-scoped state.

- [ ] `CharacterState` table (replaces per-session `SessionVars` for character data)
- [ ] `WorldState` table (global state: weather, time, resources, locations)
- [ ] `reduce_event` writes to shared world state, not session silos
- [ ] Location-scoped event queries (characters see events at their location)
- [ ] Migration path: v3 sessions map to v4 characters; existing saves importable

#### M2: World Heartbeat

Autonomous simulation loop independent of player turns.

- [ ] Background timer runs `tick_world_simulation` every N minutes (configurable)
- [ ] Weather, time-of-day, resource decay/regen advance on heartbeat
- [ ] NPC routine system — agents with schedules, needs, and locations
- [ ] Heartbeat event log (visible to players who query recent history)
- [ ] Feature flag: `WW_ENABLE_WORLD_HEARTBEAT` (default off)

#### M3: Agent Residents (via OpenClaw)

LLM agents as permanent world citizens. NPC residents are implemented as
[OpenClaw](https://github.com/openclaw/openclaw) agents, not as an internal
subsystem. WorldWeaver owns world state; OpenClaw owns the agent loop.

- [ ] `worldweaver_action` OpenClaw skill — wraps the `/action` API call
- [ ] `worldweaver_perceive` OpenClaw skill — reads world state at agent's location
- [ ] OpenClaw agent identity: persistent character with name, traits, goals (OpenClaw memory)
- [ ] Heartbeat-driven wake cycle: OpenClaw heartbeat calls perceive → decide → act
- [ ] Multiple concurrent OpenClaw agents targeting the same WorldWeaver session/world
- [ ] Agent profiles as OpenClaw SKILL.md configurations (supersedes playtest `UserProfile`)

#### M4: Situation Detection

Replace static storylets with emergent situation recognition.

- [ ] Situation detector: scans local world state for narrative-interesting patterns
- [ ] Pattern library: confrontation, scarcity, encounter, environmental shift, social tension
- [ ] Narrator prompt shift: observation-driven (describe what is) vs. theme-driven (tell a story)
- [ ] Situations as first-class objects with lifecycle (detected, active, resolved)
- [ ] Graceful coexistence: storylets and situations can both exist during transition

#### M5: Multiplayer

Multiple human players in the shared world.

- [ ] Character creation/selection on connect
- [ ] Presence system: who/what is at each location
- [ ] Concurrent action handling: temporal ordering, first-commit-wins for contested resources
- [ ] Location-scoped narrative: each player sees events relevant to their position
- [ ] Player-to-player interaction narrated by scene narrator

### V4 Non-Goals

- Real-time multiplayer (turns remain async).
- Unbounded world size (bounded geography with edge growth).
- Combat system (consequences are narrative, not mechanical).
- Pre-authored quest lines (all narrative is emergent).

---

## Major Queue

*Empty — v3 majors complete. V4 milestones tracked above.*

## Minor Queue

*Empty — v3 minors complete. V3.5 gaps tracked above.*

## Completed Work (v3 cycle)

Architecture block:

1. ✅ Minor `113` — narrator/referee temp call-site audit.
2. ✅ Major `109` — unified turn pipeline: `turn_source`/`pipeline_mode` on every turn; choice-button turns consequence-grounded via `chosen_action`; `ack_line` in diagnostics.
3. ✅ Major `108` — unified `/session/start` route; `turn_source="initial_scene"` in diagnostics.
4. ✅ Minor `112` — turn-source stratified harness metrics (choice vs. freeform split).

Sweep infrastructure block:

5. ✅ Minor `115` — clarity distribution quality gate; `clarity_distribution_score`/`clarity_health_check`; documented in `10-SWEEP_METRICS_RUBRIC.md`.
6. ✅ Major `110` — lane-stratified sweep axes; `llm_narrator_temperature`/`llm_referee_temperature` LHS axes replacing legacy `llm_temperature`.
7. ✅ Major `111` — projection quality and clarity in composite score; six-component formula; `projection_health_summary` and `clarity_ranked_results` in phase summaries.
8. ✅ Minor `114` — per-lane harness diagnostics: `narrator_parse_success_rate`, `referee_decision_valid_rate`, `narrator_revise_decision_rate`.
9. ✅ Minor `116` — batched world storylet generation; token-budget truncation fix; batches of 6 with cross-batch deduplication.
10. ✅ Minor `117` — clarity in composite score; weight 0.10; latency 0.10→0.05, projection 0.15→0.10.
11. ✅ **Major `104`** — lane-matrix and projection-budget sweeps operationalized; `LaneBudgetVariant` axis cross-product; `_validate_shared_seed_schedule` fairness guard; `lane_budget_axes`/`seed_schedule`/`quality_gate_outcomes` in phase-A manifest; `_rank_phase_results_by_projection_efficiency` secondary ranking; 23 harness integration tests; lane-matrix CLI examples in README and Gate 5a in `04-QUALITY_GATES.md`.

Hardening block:

12. ✅ Major `105` — AdvancedStateManager modularized into 4 typed domain components.
13. ✅ Minor `106` — state-domain contract tests and migration fixtures.
14. ✅ Major `106` — schema-first world-fact channel via WorldFactPayload; `fact-audit` CLI command.
15. ✅ Minor `107` — graph-fact dedupe and canonical entity audit command.
16. ✅ Minor `108` — world-fact parser failure telemetry and fallback reasons.
17. ✅ Major `107` — adaptive projection pruning with pressure tiers; `budget_exhaustion_cause` tracking.
18. ✅ Minor `109` — projection budget pressure metrics in runtime and harness context_summary.
19. ✅ Minor `105` — v3 smoke gate docs + commands; Gate 2a in `04-QUALITY_GATES.md`.
20. ✅ Minor `110` — long-run soak scenarios; Gate 6 documented.
21. ✅ **Minor `111`** — bootstrap critical-path doc (`11-BOOTSTRAP_CRITICAL_PATH.md`); `bootstrap_diagnostics` field in `SessionBootstrapResponse`/`SessionStartResponse`; 2 contract tests.

## Notes

- All v3 queue items are archived in `improvements/majors/archive/` and `improvements/minors/archive/`.
- Historical implementation evidence remains in `improvements/history/`.
- V3 prioritizes coherence, canon safety, and reproducible evaluation over feature breadth.
- 807 tests pass, `quality-strict` clean (14 warnings, all within budget).
- Frontend v3 stub anchors are in place at `client/src/app/v3NarratorStubs.ts` and `client/src/hooks/useTurnOrchestration.ts` to guide world/scene/player narrator integration without changing current behavior.
