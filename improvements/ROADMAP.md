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

- Agent never changes location in playtests — choices don't include location transitions when action pipeline generates them (vs. storylet-authored choices which do).
- `intent` field consistently null in choices — Stage B narrator not populating it.

---

## V3.5 Major: Unified Turn Pipeline

**Root cause**: `/action` and `/next` are parallel 500-line pipelines that never
share narration, JIT generation, or pool growth. JIT persistence only fires
from `/next`; the `/action` staged pipeline bypasses storylets entirely.
`active_storylets_count: 0` on every action turn.

**Goal**: One `process_turn` method. Freeform text and choice buttons enter
the same spine. Every turn can fire JIT, select storylets, and grow the pool.

Feature flag: `WW_ENABLE_UNIFIED_TURN_PIPELINE` (default `False`).

### Phase 0: Extract Shared Helpers (no behavior change)

Pure refactors — extract duplicated sub-phases into module-level functions.
Each is independently testable by running the existing suite before and after.

- [ ] `_commit_inbound_vars(db, state_manager, vars_dict)` — shared var-commit logic (action lines 652-660, next lines 1135-1149)
- [ ] `_commit_choice_selection(db, state_manager, payload)` — choice-taken commit + pending storylet choice effects (next lines 1151-1189)
- [ ] `_build_diagnostics_payload(...)` — both paths assemble ~15-key diagnostic dicts identically
- [ ] `_assemble_final_response_vars(contextual_vars, diagnostics, hint_payload)` — `_ww_diag`/`_ww_hint` injection + key prioritization
- [ ] `_run_simulation_tick(db, state_manager, session_id, storylet_id, world_memory)` — `tick_world_simulation` + conditional `reduce_event(SimulationTickIntent)` + event recording

### Phase 1: Unified Turn Input Contract

- [ ] `UnifiedTurnInput` dataclass — normalizes both `ActionRequest` and `NextReq` into one internal representation
- [ ] `from_action_request()` and `from_next_request()` factory classmethods
- [ ] Unit tests for both factories

### Phase 2: Implement `process_turn` — The Unified Spine

The single method with 10 phases:

```
1. IDEMPOTENCY CHECK (action only — hard early-return)
2. LOAD STATE + commit inbound vars/choice
3. SCENE CARD BUILD
4. INTENT EXTRACTION (action only — Stage A)
5. STATE COMMIT (action: FreeformActionCommittedIntent; next: already done in #2)
6. NARRATION SOURCE SELECTION (the key branch):
   - action turn → render_validated_action_narration (Stage C)
   - JIT eligible → generate_next_beat + persist beat
   - else → ensure_storylets + pick_storylet + adapt_storylet + fire effects
7. CHOICE NORMALIZATION
8. POST-NARRATION BOOKKEEPING (arc, motifs, hints, world_memory event)
9. RESPONSE ASSEMBLY (diagnostics, vars, projection invalidation)
10. PERSIST (save_state, idempotent response)
```

- [ ] Implement `process_turn` on `TurnOrchestrator`
- [ ] Integration tests calling `process_turn` with action input
- [ ] Integration tests calling `process_turn` with next input
- [ ] Verify output shape matches legacy methods for both input types

### Phase 3: Wire Old Methods as Thin Wrappers

- [ ] `process_action_turn`: if flag on, delegate to `process_turn`; else legacy
- [ ] `process_next_turn`: if flag on, delegate to `process_turn`; else legacy
- [ ] Full test suite green with flag off (legacy) AND flag on (unified)

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
| JIT early-return breaks phase sequence | JIT becomes a narration strategy in Phase 6, not an early-return; Phases 7-10 always run |
| Simulation tick ordering differs | Unify to always run after Phase 6 (later = safer, all mutations visible) |
| Response shape mismatch | Phase 3 wrappers project into expected shape; unified shape is internal |
| Storylet fire effects (next only) | Phase 6 storylet branch runs them; action branch skips — clean conditional |

### Rollback

Flag defaults to `False`. Flipping it off restores all legacy behavior instantly.
Legacy code removed only after unified pipeline validated in production sweeps.

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

#### M3: Agent Residents

LLM agents as permanent world citizens.

- [ ] Agent identity: persistent character with name, traits, goals, inventory
- [ ] Agent loop: wake on heartbeat, perceive surroundings, decide, act via `/action`
- [ ] Multiple concurrent agents on one server
- [ ] Agent profiles (evolved from playtest harness `UserProfile`)
- [ ] Agent-to-agent interaction at shared locations

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
