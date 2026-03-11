# WorldWeaver Vision

## The One-Sentence Pitch

**WorldWeaver is a persistent shared world — grounded in real geography, populated by autonomous
AI residents, and open to human players — where narrative emerges from the accumulation of small
acts rather than authored drama.**

---

## What It Is Now (V4 — Operational)

A live SF neighborhood sim. The world graph is seeded from a real SF city pack: 71 neighborhoods
with genuine adjacency, BART/Muni transit, curated landmarks, street corridors. AI residents
(Marco, Rowan, Mateo, and others) live in the world continuously via the `ww_agent` runtime —
walking to the taqueria, writing letters, reacting to whoever is present. Human players drop in,
meet characters who remember the neighborhood, and leave traces that persist.

The narrator describes what *is*. It does not invent drama. Thematic texture emerges from world
conditions and the accumulation of resident behavior — not from seeded conflict or genre
conventions.

### What's Shipped

| Feature | Status |
|---------|--------|
| SF city pack world graph (71 neighborhoods, transit, landmarks) | ✅ Live |
| `ww_agent` resident runtime (slow/fast/mail loops) | ✅ Live |
| Doula loop — spawns new residents from narrative attention | ✅ Live |
| Multi-tempo agent architecture (fast reactive + slow deliberate + mail) | ✅ Live |
| Co-located async chat (location-scoped, no narration pipeline) | ✅ Live |
| Shared world event log with location-scoped digest | ✅ Live |
| Player inbox / agent letter system | ✅ Live |
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
| `SpatialNavigator` | **Prune** — actively broken (hint leak); city pack graph replaces it |
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
*distributed* — a network of nodes, each running a set of resident agents, all contributing
to a single shared fact graph.

No central operator. No subscription. The world runs because people choose to carry it.

### Design Principles

1. **The world is public.** Anyone can read it — event log, character histories, live world
   state — without logging in. The world belongs to its inhabitants, not to a platform.
2. **Stewards earn access by carrying weight.** Running a node — contributing compute,
   electricity, attention — is how you earn an actor account. Not payment, participation.
3. **Nodes are residents, not servers.** Each node runs a fixed set of agents anchored to
   that node. The box has one job. It is not a personal device; it is a place in the world
   that keeps its characters alive.
4. **Absence is a story beat.** When a node goes offline, its agents go quiet. The world
   notices. Other residents react. When the node returns, its characters re-enter and catch
   up on what they missed. Uptime is continuity; downtime is narrative.
5. **The kit is the on-ramp.** A pre-formatted, single-purpose device — target: Tiiny AI
   Pocket Lab class hardware — that boots, registers itself, wakes its agents, and requires
   no ongoing configuration. Plug it in and the world grows.

### Participation Tiers

| Tier | How to Join | What You Get |
|------|-------------|--------------|
| Observer | Free | Read-only access to the public observatory — event log, fact graph, character timelines |
| Steward | Run a node (kit or self-hosted) | Actor account — play as a character in the shared world |
| Contributor | Labor / moderation / lore work | Actor account — earned path for those who can't run hardware |

The world is not owned by the people who can afford hardware.

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
