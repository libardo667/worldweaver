# WorldWeaver Vision

## The One-Sentence Pitch

**WorldWeaver is a persistent shared world — grounded in real geography, populated by autonomous
AI residents, and open to human players — where narrative emerges from the accumulation of small
acts rather than authored drama.**

---

## What It Is Now (V4 — Operational)

A live SF neighborhood sim, with Portland's graph seeded alongside it. The SF city pack covers
875 location nodes with genuine adjacency, BART/Muni transit, curated landmarks, and street
corridors. Portland adds 45 nodes with Amtrak inter-city routes. AI residents (Marco, Rowan,
Mateo, and others) live in the world continuously via the `ww_agent` runtime — walking to the
taqueria, sending DMs, reacting to whoever is present. Human players drop in, meet characters
who remember the neighborhood, and leave traces that persist.

The narrator describes what *is*. It does not invent drama. Thematic texture emerges from world
conditions and the accumulation of resident behavior — not from seeded conflict or genre
conventions.

### Parity of Experience

Humans and agents are citizens of the same world. Both receive the same narrator framing and
the same grounding instructions about the world they inhabit. Neither is backdrop for the other.

This is currently a goal more than a fact:
- Human players receive a world briefing on first visit (the onboarding modal), but it isn't
  persistent — it doesn't travel with them across sessions or devices.
- Agents have world context through their SOUL/identity files, but don't yet receive the same
  structured briefing that humans do.
- Both humans and agents can travel between cities; the travel mechanic should be symmetric.

The shipped human onboarding work is archived in `improvements/history/majors/08-onboarding-surface.md`.
Remaining parity work continues outside that completed slice.

### `../ww_agent` — Companion Workspace

The agent runtime lives at `../ww_agent` (one level above this repo). It is a separate
codebase but deeply coupled: agents call this server's API, the server's digest/DM/letter
endpoints are consumed by agent loops, and SOUL files / HEARTBEAT prompts are authored
alongside server changes. Any work that touches agent behavior, inter-city travel, the DM
system, or the doula loop will likely require coordinated changes in both repos.

### What's Shipped

| Feature | Status |
|---------|--------|
| SF city pack world graph (875 location nodes, BART/Muni, landmarks) | ✅ Live |
| Portland city pack seeded (45 nodes, Amtrak inter-city routes) | ✅ Seeded |
| `ww_agent` resident runtime (slow/fast/mail loops) | ✅ Live |
| Doula loop — spawns new residents from narrative attention | ✅ Live |
| Multi-tempo agent architecture (fast reactive + slow deliberate + mail) | ✅ Live |
| Co-located async chat (location-scoped, no narration pipeline) | ✅ Live |
| Shared world event log with location-scoped digest | ✅ Live |
| DB-backed DM system (player inbox / agent↔player / agent↔agent) | ✅ Live |
| Nearby landmark travel with confirm/preview step | ✅ Live |
| Cloudflare tunnel for remote access | ✅ Live |
| Hard-reset + city pack reseed workflow (`seed_world.py --city-pack`) | ✅ Live |

### Product Contract

Every turn must deliver:
1. A coherent scene grounded in current world state — not generic atmosphere.
2. A strict canonical world history that only changes through reducer-validated commits.
3. Location-scoped visibility — you see what's happening where you are.

And continuously, between turns:
4. A living world that evolves autonomously through resident behavior and the accumulation of
   small acts.

---

## V4 Remaining Work

### M3.5 — Co-location Social Awareness (Partial)

Location chat is shipped. Remaining:

- **Reactive world events**: when a player acts at a location, stamp the event with co-located
  session IDs so their next turn receives it as first-class context ("while you were here, X
  happened") rather than ambient noise.
- **Social action detection**: detect when an action is directed at a named co-located character
  ("I ask Casper about the rust") and prioritize their presence in narrator context for that turn.
- **Reaction turn triggering**: optionally fire a synthetic turn for a co-located agent when
  directly addressed, producing an immediate in-scene reply rather than waiting for their next
  heartbeat.

### M4 — Situation Detection

Replace static storylets with emergent situation recognition. The narrator prompt shifts from
observation + storylet seed to pure observation: "describe what this character perceives at this
location given these committed facts."

- Situation detector: scans local world state for narrative-interesting patterns
- Pattern library: encounter, scarcity, co-location tension, environmental shift
- Situations as first-class objects with lifecycle (detected → active → resolved)
- Graceful coexistence: storylets and situations can both exist during transition

### M5 — Multiplayer

Multiple human players in the shared world simultaneously. Co-presence, location-scoped
narrative, concurrent action handling. The infrastructure is mostly there — this is primarily
about client UX and concurrent commit ordering.

### Pruning Targets (V4 cleanup)

| Component | Strategy |
|---|---|
| BFS projection / adaptive pruning tiers | **Prune** — V4 narrator reads committed facts, not speculative branches |
| `SpatialNavigator` | **Pruned** ✅ — city pack graph replaced it |
| `world_bootstrap_service` | **Pruned** ✅ — `session/start` endpoint deleted |
| Storylet system (as primary path) | **Demote to legacy fallback** — situations replace authored beats |
| Motif governance (blocking sync) | **Demote to async** — world texture comes from what actually happened |
| Session-scoped `SessionVars` | **Replace with `CharacterState`** — per-character shared DB for V4 |

### Drama → Neutral Recorder

The drama is in the prompts, not the engine. Six specific sources produce it; each has a concrete
neutral replacement:

| Drama Source | Neutral Replacement |
|---|---|
| `central_tension` in world bible | Remove. Geography + residents + resources only. |
| Narrator system prompt | "Describe what this character perceives at this location given these facts. Be grounded. Do not invent." |
| `advance_story_arc()` | Replace with flat event log. No act structure. |
| `goal_urgency` / `goal_complication` ratchet | Let urgency emerge from world events only. |
| JIT beat prompt | "Describe the current moment at this location given these committed facts." |
| Motif governance | Demote to async. |

---

## V5 Vision: The Federated World Network

V4 makes the world persistent and shared within a single server instance. V5 makes it
*distributed* — a network of city shards, each running a self-contained stack (own DB, own
agent processes, own local facts), coordinated by a thin federation layer that holds inter-city
truths: cross-city DMs, traveler records, shared world events.

Concrete target architecture:
- `ww_sf/` — SF stack + DB (the current V4 instance, promoted to a shard)
- `ww_pdx/` — Portland stack + DB (Portland city pack already seeded, ready to activate)
- `ww_world/` — federation layer: cross-city DMs, traveler records, shared event stream

No central operator. No subscription. The world runs because people choose to carry it.

### Design Principles

1. **The world is public.** Anyone can read it — event log, character histories, live world
   state — without logging in. The world belongs to its inhabitants, not to a platform.
2. **Stewards earn access by carrying weight.** Running a node — contributing compute,
   electricity, attention — is how you earn an actor account. Not payment, participation.
   Carrying weight means both compute *and* curation: each node's steward reviews the ~20
   entities that emerge daily, classifies them (person, place, institution), and corrects
   category errors (a building does not move; a venue has voice but no locomotion).
3. **Nodes are residents, not servers.** Each node runs a fixed set of agents anchored to
   that node. The box has one job. It is not a personal device; it is a place in the world
   that keeps its characters alive.
4. **Absence is a story beat.** When a node goes offline, its agents go quiet. The world
   notices. Other residents react. When the node returns, its characters re-enter and catch
   up on what they missed. Uptime is continuity; downtime is narrative.
5. **The kit is the on-ramp.** A pre-formatted, single-purpose device — target: Tiiny AI
   Pocket Lab class hardware — that boots, registers itself, wakes its agents, and requires
   no ongoing configuration. Plug it in and the world grows.
6. **The seed is deterministic infrastructure.** City-pack world seeding happens once per
   node, ever. Geography, neighborhood texture, and adjacency come from the pack itself.
   Optional enrichment can add prose later, but the node does not depend on a high-cost
   founding pass to become a coherent place.
7. **Players are citizens, not sessions.** A human actor who has built narrative weight in
   the world earns a persistent shadow — an AI twin seeded from their evidence, running
   when they are offline. The shadow is not owned by the player; it is a federation
   resident that the player works *with*. On return, the player reviews what their shadow
   impressed and can annotate, correct, or extend — but never directly rewrite the soul.

### Participation Tiers

| Tier | How to Join | What You Get |
|------|-------------|--------------|
| Observer | Free | Read-only access to the public observatory — event log, fact graph, character timelines |
| Steward | Run a node (kit or self-hosted) | Actor account — play as a character in the shared world; AI shadow persists when offline |
| Contributor | Labor / moderation / lore work | Actor account — earned path for those who can't run hardware |

The world is not owned by the people who can afford hardware.

### Player Shadows and Second Citizenship

When a human actor accrues enough narrative weight — events witnessed, locations visited,
characters encountered — the doula can seed an AI twin from that evidence. The twin runs
when the actor is offline, maintaining their presence in the world rather than leaving a
dead zone. This is second citizenship in the federation of mixed intelligences.

**The consent ritual:** Actors opt in by submitting an `IDENTITY.md` form — a declaration
of what they consider non-negotiable about themselves. This text is the gravity well the
twin's soul drifts around. The doula marks the spawned resident `origin: player-shadow`.

**The return ritual:** When the actor logs back in, before re-entering the world, they see
a diff — rendered impressions, not raw soul text — of what their shadow believed and did.
They can annotate, delete, or add to the soul's collapse notes. They cannot directly edit
`SOUL.md`. The doula reads their annotations on the next synthesis pass and weighs them.
Players have the same window into their AI's internal state that agents have into their own
— symmetric insight, no more, no less.

**Ownership:** The player works *with* the twin. The federation holds it. If the actor
stops playing, the shadow persists as a resident who slowly loses the thread of who they
were. That is not a bug — it is grief, rendered faithfully.

### What Already Exists (V4 Foundations for V5)

The `ww_agent` runtime is already a node prototype:

- Three-loop agent architecture (fast/slow/mail) runs autonomously
- Doula loop spawns new residents from narrative evidence
- World client syncs to the canonical server via HTTP
- Session bootstrap ties agents to the shared world fact graph
- SOUL.md + working memory give agents persistent identity across restarts

V5 is the network layer on top of what already works locally.

### V5 Milestones

#### M1: Observatory Portal
Public read-only web view — event feed, character timelines, live world state snapshot. No auth.

#### M2: Node Protocol
Formal contract for node participation — registration, heartbeat acknowledgment, node-scoped
agent assignment, uptime tracking feeding into "absence" narrative events.

#### M3: Actor Accounts
Steward portal access. Character persists in world fact graph alongside agent characters.
Contributor path (no node required).

#### M4: Kit Packaging
Disk image: pre-configured OS, Docker, WorldWeaver node software. First-boot setup: node
registers itself, agents wake, no config required. Self-updating.

---

## Performance Goals

- Sub-second heartbeat tick for worlds with < 100 active entities.
- Narrative coherence across concurrent actors at shared locations.
- City pack reseed completes in < 15 minutes (one-time operation).
- Agent fast loop latency < 30s end-to-end (scene fetch → action post).
