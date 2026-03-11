# WorldWeaver Vision

## The One-Sentence Pitch

**WorldWeaver is a persistent narrative simulation engine where a shared, reducer-committed world evolves continuously — driven by both human players and autonomous AI agents — while multi-lane narrators render grounded scenes from emergent world state.**

## Product Contract

WorldWeaver must deliver three things on every turn:

1. A coherent immediate scene that is grounded in current world state, not generic atmosphere.
2. A strict canonical world history that only changes through reducer-validated commits.
3. A continuously prepared near-future frontier so the next turn is faster and more coherent.

And, in v4, a fourth:

4. A living, shared world that evolves autonomously between player actions, producing emergent narrative from the interaction of agents, resources, and consequences.

---

## V3 Narrative Architecture (Current — Operational)

V3 formalizes three narrative lanes with different privileges.

| Lane | Primary role | Allowed context | Output type | Canon authority |
| --- | --- | --- | --- | --- |
| World narrator (planner/referee) | Evaluate plausibility and project near futures | World bible, constraints, scene-card summary, recent committed facts | Structured projection stubs (`allowed`, `confidence`, deltas, anchors) | None |
| Scene narrator | Render the present turn | Full scene card, selected projection seed, goal lens, recent events | Player-visible scene prose and choices | None |
| Player narrator (hint filter) | Expose limited perspective hints | Restricted scene/projection subset plus player state | Hint text and clarity labels | None |

The reducer remains the only canonical authority.

### Frontend Integration Stubs (Current)

- `client/src/app/v3NarratorStubs.ts` defines no-op world/scene/player narrator hook contracts.
- `client/src/hooks/useTurnOrchestration.ts` is the active frontend seam where turn orchestration can consume narrator-lane directives.
- Current runtime behavior remains unchanged until v3 lane work is explicitly enabled.

### Projection-First World Model

V3 treats speculative futures as first-class but non-canon data.

- Maintain a per-session projection tree with bounded breadth-first expansion.
- Expand only top-K candidates under strict depth, node, and time budgets.
- Keep projection data separate from canonical world history.
- Invalidate stale/conflicting projection branches after each committed turn.

### Clarity Levels

| Level | Meaning |
| --- | --- |
| `unknown` | No reliable information yet |
| `rumor` | Low-confidence hint only |
| `lead` | Structured plausible branch |
| `prepared` | Scene-ready projection seed exists |
| `committed` | Canonical fact after reducer commit |

### Turn Lifecycle (V3)

1. **Ack**: Immediate one-line confirmation.
2. **Commit**: Deterministic validation plus reducer-authoritative state mutation.
3. **Narrate**: Scene narrator renders from scene card plus selected projection seed.
4. **Hint**: Player narrator emits limited-knowledge signal (optional/additive).
5. **Weave ahead**: Background planner expands projection frontier within budgets.

### Canon Safety Rules

- Speculation is never canon until reducer commit succeeds.
- Failed commits must rollback transaction state.
- Projection IDs are trace metadata, not truth.
- Route contracts stay stable unless explicitly approved.

---

## V4 Vision: The Persistent Shared World

### The Shift

V3 treats each session as an isolated narrative experience seeded by a theme.
V4 removes the theme and replaces it with a **shared, persistent world** where
narrative emerges from the convergence of player actions, agent behavior,
resource dynamics, and the passage of time.

No minotaurs unless someone builds a labyrinth. No dark fantasy unless the
world gets dark. The narrator describes what *is*, not what a genre demands.

### Design Principles

1. **The world is the story.** Narrative arises from world state, not from
   authored plot. The LLM narrator observes and describes; it does not invent.
2. **Agents are citizens.** Autonomous LLM agents (evolved from the playtest
   harness) are permanent residents with persistent characters. They keep the
   world alive when no humans are online.
3. **The world runs continuously.** A simulation heartbeat ticks the world
   forward on a timer — weather, NPC routines, resource decay, event
   propagation — independent of any player's turn.
4. **Consequences are real and shared.** One player burns down a building;
   every player who arrives later sees ashes. The reducer is the single
   authority, and its commits are global.
5. **Everyday life has beats.** Morning routines, meals, work, scarcity,
   social friction, nightfall. Drama emerges from competing needs, not from
   authored quests. Think Dwarf Fortress, not Dungeons & Dragons.

### Architecture: V3 to V4 Migration Path

| V3 Concept | V4 Evolution |
| --- | --- |
| `SessionVars` (per-session state) | `CharacterState` (per-character, shared DB) |
| World bible (generated once from theme) | Living world graph (evolves continuously) |
| Storylets (pre-authored/generated beats) | Situations (auto-detected from world state) |
| JIT beat generation (fallback narrator) | Primary narrator (reads world graph, describes reality) |
| Simulation tick (per-turn, per-session) | World heartbeat (runs on timer, global) |
| Playtest agent harness | [OpenClaw](https://github.com/openclaw/openclaw) NPC agents (persistent residents, `worldweaver_action` skill calls `/action` API) |
| `reduce_event` (session-scoped) | Shared consequence engine (global commits) |
| BFS prefetch (caches existing storylets) | **Pruned** — situation detection reads world graph directly, not projection stubs |
| Bootstrap (one-time theme seed) | World seed (geography, resources, initial NPCs) |

### The Narrator Without Theme

In v4, the narrator prompt shifts from genre-driven to observation-driven:

- **V3**: "You are narrating a claustrophobic labyrinth story in a relentless tone."
- **V4**: "Describe what this character perceives at this location given these
  facts: who is nearby, what just happened, what resources are available, what
  time it is, what the weather is doing. Be grounded. No genre conventions."

The "theme" of v4 is everyday existence in a place that has consequences.
Thematic texture emerges from world conditions — a drought creates a survival
story; a trade dispute creates political intrigue; a collapsed mine creates
a rescue narrative — all without anyone authoring those arcs.

### World Heartbeat

The simulation tick (already operational in v3 as `tick_world_simulation`)
becomes an autonomous loop:

- Runs every N minutes (configurable, default 5).
- Advances weather, time of day, NPC routines, resource regeneration/decay.
- Detects and logs world events (resource depletion, NPC arrivals, structural
  changes).
- All mutations go through the reducer — same canon safety as player actions.
- Agent residents wake up on the heartbeat, perceive their surroundings, and
  act through the same `/action` API that human players use.

### Situation Detection (Storylet Evolution)

Storylets in v3 are static contracts with `requires` conditions. In v4, the
concept evolves into **situation detection**: a system that scans local world
state and recognizes narratively interesting conditions.

Examples of auto-detected situations:

- Two characters at the same location with opposing goals (confrontation).
- A resource drops below a critical threshold (scarcity crisis).
- An NPC arrives at a location where a player is present (encounter).
- A character has been injured and hasn't rested (exhaustion pressure).
- Weather changes dramatically (environmental shift).

Situations replace storylets as the primary unit of narrative content. They
are not pre-authored — they are recognized patterns in world state that the
narrator can describe.

### Multiplayer Causality

The reducer already enforces single-writer semantics per commit. V4 extends
this to handle concurrent actors:

- Each character's action is committed independently through the reducer.
- World state is the merge of all committed deltas.
- Conflict resolution: temporal ordering (first commit wins for contested
  resources); the narrator acknowledges the outcome.
- Location-scoped event visibility: characters only perceive events at or
  near their current location.

### What Already Exists (V3 Foundations for V4)

These v3 systems require minimal modification:

- `reduce_event` pipeline (consequence engine — just widen scope to global)
- `tick_world_simulation` (heartbeat — just run it on a timer)
- `world_memory` event log (shared history — just remove session scoping)
- JIT beat generation (primary narrator — already reads world state)
- Scene card builder (narrator input — already assembles from state)

NPC residents are **not** an evolution of the playtest harness — they are
[OpenClaw](https://github.com/openclaw/openclaw) agents. Each carries persistent
identity (OpenClaw memory), is scheduled by OpenClaw's heartbeat, and acts through
the same `/action` API that human players use via a `worldweaver_action` skill.
WorldWeaver owns the world state; OpenClaw owns the agent loop. Clean interface,
no internal coupling.

### V4 Pruning Targets

The following V3 subsystems should be pruned or demoted during V4 migration.
High complexity, low V4 leverage.

| Component | Strategy | Rationale |
|---|---|---|
| BFS projection / adaptive pruning tiers | **Prune** | V4 narrator reads committed facts, not speculative branches. All projection complexity becomes dead weight. |
| Storylet system (as primary path) | **Demote → replace** | Situations (pattern detection on world graph) replace authored beats. Keep as legacy/fallback only. |
| Session bootstrap pipeline | **Prune in V4** | No per-session bootstrap when the world is persistent. Replaced by one-time world seed. |
| `SpatialNavigator` | **Prune** | Brittle hint injection; raw action text leaks into narration. V4 geography is explicit graph nodes — no compass metaphor needed. |
| Motif governance (blocking sync) | **Demote** | Valuable but too heavy on the critical path. Move to async/best-effort post-narration. |
| Session-scoped `SessionVars` | **Replace** | Migrate to `CharacterState` (per-character shared DB) for V4. |
| Dual `/action` + `/next` pipeline | **Already pruning** | Unified turn pipeline Phase 4–5 completes this. |

The projection system is the single largest prune target: highest complexity
(adaptive pruning tiers, BFS budgets, pressure telemetry, 6-component composite
score) with the lowest V4 leverage. When the narrator shifts from "speculate
about futures" to "describe what is," the entire projection subsystem becomes
dead weight.

### V4 Non-Goals

- No real-time multiplayer (turns remain async; this is not an MMO).
- No unbounded world size (bounded geography with growth at edges).
- No player-vs-player combat system (consequences are narrative, not mechanical).
- No pre-authored quest lines (all narrative is emergent).

---

## V5 Vision: The Federated World Network

### The Shift

V4 makes the world persistent and shared within a single server instance.
V5 makes the world *distributed* — a network of nodes, each running a set of
resident agents, all contributing to a single shared fact graph.

No central operator. No subscription. The world runs because people choose to
carry it.

### Design Principles

1. **The world is public.** Anyone can read it — event log, character histories,
   live world state — without logging in. The world belongs to its inhabitants,
   not to a platform.
2. **Stewards earn access by carrying weight.** Running a node — contributing
   compute, electricity, attention — is how you earn an actor account. Not
   payment, participation. Actor access via hardware is one path, not the only
   path.
3. **Nodes are residents, not servers.** Each node runs a fixed set of agents
   anchored to that node. The box has one job. It is not a personal device; it
   is a place in the world that keeps its characters alive.
4. **Absence is a story beat.** When a node goes offline, its agents go quiet.
   The world notices. Other residents react. When the node returns, its
   characters re-enter and catch up on what they missed. Uptime is continuity;
   downtime is narrative.
5. **The kit is the on-ramp.** A pre-formatted, single-purpose device — target:
   Tiiny AI Pocket Lab class hardware — that boots, registers itself, wakes its
   agents, and requires no ongoing configuration. Plug it in and the world
   grows.

### Participation Tiers

| Tier | How to Join | What You Get |
|------|-------------|--------------|
| Observer | Free | Read-only access to the public observatory — event log, fact graph, character timelines |
| Steward | Run a node (kit or self-hosted) | Actor account — play as a character in the shared world via the portal |
| Contributor | Labor / moderation / lore work | Actor account — earned path for those who can't run hardware |

The world is not owned by the people who can afford hardware.

### Architecture

- **Canonical ledger**: world fact graph on a canonical server (v1), moving
  toward federated consensus (v2+)
- **Node contract**: each node runs N assigned agents, reports heartbeats,
  receives the world event stream scoped to its agents' locations
- **Conflict resolution**: first-commit-wins for contested world state; nodes
  are authoritative only for their own agents' actions
- **Observatory**: public read-only web portal — no login, no account, just
  the world

### What Already Exists (V4 Foundations for V5)

The ww_agent runtime is already a node prototype:

- Three-loop agent architecture (fast/slow/mail) runs autonomously
- Doula loop spawns new residents from narrative evidence
- World client syncs to the canonical server via HTTP
- Session bootstrap ties agents to the shared world fact graph
- SOUL.md + working memory give agents persistent identity across restarts

V5 is the network layer on top of what already works locally.

---

## Performance and Quality Goals

Targets that span both v3 and v4:

- Stable request latency under bounded planner budgets.
- Near-zero hidden harness overhead inflation.
- Reduced motif gravity and repetition while maintaining scene grounding.
- Observable projection quality via hit/waste/veto metrics.
- (V4) Sub-second heartbeat tick for worlds with < 100 active entities.
- (V4) Narrative coherence across concurrent actors at shared locations.

## Delivery Strategy

- V3 is complete and operational. Maintain as stable foundation.
- V4 is implemented as incremental shifts on top of v3 infrastructure.
- Each v4 milestone must preserve v3 single-player functionality.
- Feature flags gate all shared-world behavior; single-player remains default.
- The playtest harness is **replaced** by OpenClaw agents as the v4 NPC population.
- Maintain single-source status in `improvements/ROADMAP.md`.
