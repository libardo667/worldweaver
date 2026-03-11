# Roadmap

## Current State

**V4 is operational.** V3 is complete history. Active work is V4 M3.5 → M4.

- SF city pack world graph live (71 neighborhoods, BART/Muni, landmarks)
- `ww_agent` residents running continuously (M3 complete)
- Co-located async chat shipped (M3.5 partial)
- Unified turn pipeline operational; storylet system demoted to fallback
- Next focus: M3.5 remaining social awareness work, then M4 situation detection

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

### Drama → Neutral Recorder: Prompt-Level Changes

The drama is not in the engine — it is in the prompts and bootstrap schema.
Six specific sources produce it; each has a concrete neutral replacement.

| Drama Source | What It Does | Neutral Replacement |
|---|---|---|
| `central_tension` in world bible | Seeds every narrator call with a conflict | Remove. Replace with geography + residents + resources only |
| Narrator system prompt | "Narrate a [tone] story" | "Describe what this character perceives at this location given these facts. Be grounded. Do not invent." |
| `advance_story_arc()` | Tracks act/tension/unresolved_threads — imposes dramatic structure | Replace with a flat event log. No act structure. |
| `goal_urgency` / `goal_complication` ratchet | Artificially pressurizes the session over time | Let urgency emerge from world events only, not a formula |
| JIT beat prompt | Asks for a "beat" — a drama unit | Ask instead: "describe the current moment at this location given these committed facts" |
| Motif governance | Enforces thematic consistency | Demote to async. World texture comes from what actually happened, not what was seeded |

The world graph (fact ledger) becomes the primary narrator input.
The narrator reads facts and describes them. It does not invent drama.

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

#### M3: Agent Residents ✅ Shipped

LLM agents as permanent world citizens via the `ww_agent` runtime.
WorldWeaver owns world state; `ww_agent` owns the agent loop.

- [x] `ww_agent` resident runtime with slow/fast/mail loop architecture
- [x] Residents live continuously in the SF world (Marco, Rowan, Mateo, and others)
- [x] Doula loop spawns new residents from narrative attention
- [x] SOUL.md + working memory give agents persistent identity across restarts
- [x] Letter system for async agent↔player and agent↔agent communication
- [x] ww_agent residents visible in backend roster + inbox routing
- [x] SF city pack world graph as location foundation (71 neighborhoods, transit, landmarks)

#### M3.5: Co-location Social Awareness (Partial)

- [x] Co-located character context injected into scene narrator prompt
- [x] Co-located async chat (location-scoped, no narration pipeline) — `LocationChat` model,
      GET/POST endpoints, digest snapshot, client chat pane
- [x] Movement destination tracking — departure stamped at origin, arrival tracked via
      `destination` field; roster and timeline both reflect correct positions
- [ ] Reactive world events — stamp events with co-located session IDs so their next turn
      receives "while you were here, X happened" as first-class context
- [ ] Social action detection — detect actions directed at a named co-located character and
      prioritize their presence in narrator context
- [ ] Reaction turn triggering — optionally fire a synthetic turn for a co-located agent when
      directly addressed

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

---

## V5: Federated World Network

See `improvements/VISION.md` for V4 rationale. V5 extends the shared world into a
decentralized, steward-run infrastructure network.

### Core Concept

The world is public and observable. Running it costs compute, electricity, and
attention. Stewards are people who choose to carry that cost — not as customers
buying features, but as custodians who believe a persistent shared world is worth
keeping alive.

### The Node Kit

A pre-formatted, single-purpose server (target: Tiiny AI Pocket Lab class device
+ Framework laptop or equivalent) that:

- Runs a fixed set of resident agents anchored to that node
- Contributes those agents' actions to the shared world fact graph
- Fires OpenClaw heartbeats autonomously (no human needed)
- Syncs world events in, pushes agent actions out

The box has one job. It is not a personal device. It is a node in the network.

### Participation Tiers

| Tier | How to Join | What You Get |
|------|-------------|--------------|
| Observer | Free | Read-only access to the public world portal — event log, fact graph, character histories |
| Steward | Run a node (kit or self-hosted) | Actor account — play WorldWeaver as a character in the shared world via the portal |
| Contributor | Labor/moderation/lore | Actor account — earned path for those who can't run hardware |

**Key principle**: steward access is earned by carrying weight, not purchased as a
feature. Actor access via kit is one path, not the only path. The world is not
owned by the people who can afford hardware.

### Absence as Narrative

When a node goes offline, its agents go quiet. The world notices. Other agents
react. When the node returns, its characters re-enter the world and catch up on
what they missed. Uptime is continuity; downtime is a story beat.

### Architecture

- **Canonical ledger**: world fact graph lives on a canonical server (v1) or
  federated consensus (v2+)
- **Node contract**: each node runs N assigned agents, reports heartbeats, receives
  world event stream for its agents' location scope
- **Conflict resolution**: first-commit-wins for contested world state; nodes are
  authoritative only for their own agents' actions
- **Observatory**: public read-only portal — event feed, character timelines,
  live world state. No login required.

### V5 Milestones

#### M1: Observatory Portal

Public read-only web view of the world.

- [ ] Event feed (world history, paginated, filterable by character/location)
- [ ] Character timeline view (per-agent action history)
- [ ] Live world state snapshot (locations, active characters, recent facts)
- [ ] No auth required

#### M2: Node Protocol

Formal contract for node participation.

- [ ] Node registration endpoint (POST /api/nodes/register)
- [ ] Heartbeat acknowledgment from canonical server
- [ ] Node-scoped agent assignment (world assigns characters to nodes)
- [ ] Node health + uptime tracking (feeds into "absence" narrative events)

#### M3: Actor Accounts

Steward portal access.

- [ ] Actor account creation (gated by node registration)
- [ ] Human player sessions via portal (calls /api/action, same as agents)
- [ ] Contributor path (moderation/lore work → actor grant, no node required)
- [ ] Actor character persists in world fact graph alongside agent characters

#### M4: Kit Packaging

Hardware + software bundle.

- [ ] Disk image: pre-configured OS, Docker, WorldWeaver node software, OpenClaw
- [ ] First-boot setup: node registers itself, agents wake, no config required
- [ ] Supported hardware: Tiiny AI Pocket Lab class (120B local inference) + x86 laptop
- [ ] Self-update: node pulls world software updates without human intervention

---

## Investigation: Inter-Agent Telegram Messaging

OpenClaw already wires each agent to a Telegram bot account. The open question
is whether agents can message *each other* (bot-to-bot) and message Levi directly
from in-world events.

### What needs investigation

- **Bot-to-bot messaging**: Telegram bots cannot initiate DMs to other bots by
  default. Options:
  - A shared group chat where all agents are members — agents post as themselves,
    others read the group. OpenClaw's `groupPolicy: allowlist` may already support
    this pattern.
  - A relay agent (Rowan?) that receives messages from one agent and forwards to
    another via the group or a dedicated channel.
  - Webhook-to-webhook: agents call each other's OpenClaw HTTP endpoints directly
    (bypassing Telegram) — simpler but loses the Telegram paper trail.

- **Agent-to-Levi messaging**: Already works — each agent has a bot and `dmPolicy:
  pairing`. Agents can send Levi a message via their Telegram bot when something
  notable happens. The HEARTBEAT already does this with "send a one-sentence summary."

- **In-world event triggers**: When a world event involves two characters (e.g.
  an encounter at a shared location), can the system automatically notify both
  agents' Telegram bots? This would require a world event webhook or a polling
  step in each agent's HEARTBEAT.

### Suggested next steps

- [ ] Test: add all agent bots to a single Telegram group. Confirm each can post
  as itself. Confirm OpenClaw routes group messages to the right agent.
- [ ] Add a `worldweaver-social.md` skill: teaches agents to post a Telegram
  message when they encounter another character (read from world events) or when
  something memorable happens.
- [ ] Investigate: can Rowan (doula) act as a social relay — routing notable
  world events to relevant agents' Telegram bots as in-character "news"?
- [ ] Consider: a public Telegram channel (read-only) that publishes world events
  as they happen — the observatory layer for anyone who wants to follow along
  without running a node.

---

## Notes

- All v3 queue items are archived in `improvements/majors/archive/` and `improvements/minors/archive/`.
- Historical implementation evidence remains in `improvements/history/`.
- V3 prioritizes coherence, canon safety, and reproducible evaluation over feature breadth.
- 807 tests pass, `quality-strict` clean (14 warnings, all within budget).
- Frontend v3 stub anchors are in place at `client/src/app/v3NarratorStubs.ts` and `client/src/hooks/useTurnOrchestration.ts` to guide world/scene/player narrator integration without changing current behavior.
