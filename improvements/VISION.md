# WorldWeaver Vision

## The One-Sentence Pitch

**WorldWeaver is a narrative simulation engine where AI generates a living world around you, and the stories you stumble into become permanent facts that reshape everything that follows.**

---

## What This Is

Think Dwarf Fortress meets text adventure — but you're not a god watching from above. You're just another person in the world. You start with a simple goal (deliver a package, find a missing person, survive the winter) and then *the world happens to you*. Storylets — small narrative events — fire based on where you are and what your accumulated story context looks like. Once experienced, they become permanent world history. NPCs remember. The environment changes. New storylets emerge from what's already happened.

### What makes it different from interactive fiction

Interactive fiction is a tree of authored paths. WorldWeaver is a **field of narrative possibilities** where the player's trajectory through meaning-space determines what they encounter. There's no "correct path." Two players starting with the same goal will have radically different experiences because the storylets that fired early reshape what fires later.

### The Dwarf Fortress inspiration

In DF, a world simulates forward — history accumulates, civilizations rise and fall, individual dwarves have memories and grudges. WorldWeaver does this for narrative: the world has a growing memory of what's happened, and that memory changes what can happen next. But instead of simulating physics and logistics, it simulates *story*.

---

## Core Architecture Concept: The Semantic Storylet Engine

Inspired by the Parallax project's (C:\Users\levib\OneDrive\Documents\products\ruliad-expedition-v1) approach to semantic meaning extraction and visualization.

### How storylets work today (v1)
- Storylets have hard-coded `requires` dicts (`{has_pickaxe: true}`)
- Selection: filter by requirements → weighted random pick
- Position: 2D grid coordinates for compass navigation

### How storylets should work (vision)
- Each storylet is **semantically embedded** — its text, themes, and narrative role are encoded as a vector in meaning-space
- The player's **accumulated context** (choices made, events witnessed, current goal, emotional arc) is also a vector
- **Proximity in semantic space = probability of firing** — storylets "near" your current narrative state are more likely, but distant ones still have a nonzero chance (weak connections)
- Story beats and character choices **warp the probability field** — making a morally questionable choice pulls dark-themed storylets closer; helping someone shifts the field toward community/trust storylets
- Once a storylet fires, it becomes a **permanent fact** in the world state — it changes the semantic landscape for everyone and everything

### The dual-layer world

| Layer | What it does | How you move through it |
|-------|-------------|------------------------|
| **Physical space** | Geography — towns, roads, forests, buildings | Walk, ride, sail. Compass directions. You go to the tavern. |
| **Semantic space** | Narrative possibility — what can happen here, now, to you | Your choices, your history, your goals. What happens AT the tavern depends on who you are and what you've done. |

Physical space determines *where* you are. Semantic space determines *what happens* there.

### Interaction model: Hybrid

- **Storylets present choices** — "The merchant offers you a suspicious crate. [Accept] [Refuse] [Ask what's inside]"
- **You can also type freeform** — "I peek under the tarp when the merchant isn't looking"
- The AI interprets freeform actions and resolves them against the world state, potentially triggering or modifying storylets

---

## World Memory: Persistent State

When a storylet fires, it's not just a thing that happened to the player — it's a thing that happened in the world.

- **NPCs remember** — the blacksmith you helped last week greets you differently; the thief you caught tells others about you
- **The environment changes** — the bridge you burned stays burned; the rumor you started spreads
- **Future storylets are shaped by past ones** — not through hard-coded flags, but through the semantic shift that accumulated events create in the world's meaning-space
- **History accumulates** — the world gets richer and more specific over time, not more generic

---

## Who This Is For

**Primary**: People who want to explore a world that feels alive — where things happen whether or not you're looking, and your choices matter not because a designer branched the story, but because the world's semantic fabric shifted around your actions.

**Secondary**: World-builders and authors who want to seed a world with a description and some themes, then watch it grow through play. The AI generation tools are creation-time AND runtime — the world bootstraps from a description and continues generating as players interact with it.

---

## Non-Goals

- **Not a Twine story format** — Twine is a prototype frontend, not the permanent UI. The API is the product.
- **Not a branching narrative tool** — No author-designed story trees. The "story" emerges from the interaction between player actions and the semantic field.
- **Not a multiplayer game (yet)** — Single player exploring a world that simulates depth. Multi-player is a future possibility but not a current goal.
- **Not a general-purpose game engine** — It tells stories. It doesn't do physics, combat systems, or real-time rendering.

---

## What Success Looks Like

1. A player describes a world in a few paragraphs → the system generates a navigable, semantically-rich world with dozens of storylets
2. The player starts with a simple goal → within 15 minutes, emergent events have complicated, enriched, or completely redirected that goal
3. Two players with the same starting world have meaningfully different experiences
4. Events from early play visibly influence what happens later — the world has *memory*
5. The player can type unexpected actions and the world responds coherently
6. Playing feels like exploring a place that exists independently of you, not like reading a book someone wrote for you

---


## Continuous Loading and Perceived Latency

WorldWeaver should feel responsive even when the underlying model calls are slow. The system uses a two-lane approach:

### Fast lane (player-visible, should feel immediate)
The fast lane always prioritizes **getting something coherent on screen quickly**:
- select from already-available storylets (or cached stubs),
- apply deterministic state updates,
- stream an immediate acknowledgment line and a short core outcome,
- offer follow-up choices without blocking on background work.

### Slow lane (background weaving)
In parallel, the slow lane continuously expands the nearby world so the fast lane has ammunition:
- prefetch a small frontier of nearby storylet stubs (semantic and geographic),
- embed and position new candidates,
- refresh a small pack of relevant world facts and projections,
- synthesize runtime storylets only when the context is sparse or repetitive,
- cache results with strict budgets and TTLs.

The slow lane is **additive**: it must never mutate session state directly and must never change world facts without a player-triggered commit.

### Structure-first prefetch (avoid wasting prose)
Background work generates **structure**, not long narration:
- storylet stubs (premise, requires, choices, short notes),
- embeddings and weights,
- leads and points of interest.

Narration is generated on-demand by merging a chosen stub with the player's action and validated state deltas.

### Progressive turn rendering
Turns render in phases to avoid “dead air”:
1. **Ack**: immediate 1-line confirmation of the player's intent.
2. **Commit**: deterministic validation + state/world updates.
3. **Narrate**: streamed narration and follow-up choices.
4. **Weave ahead**: background frontier prefetch continues quietly.

### Optional “world-weaving prompts”
During onboarding and long turns, the client can offer small optional prompts (first impression, hope, fear, vibe lens).
These keep the player engaged and also enrich the world seed and lens weights.

## Technical Direction

### Keep from current codebase
- FastAPI backend, SQLite, Pydantic schemas
- Storylet data model (extend, don't replace)
- Session/state management patterns
- LLM service integration
- Auto-improvement pipeline concept (smoothing/deepening)

### Evolve
- **Storylet selection**: from `requires` dict matching → semantic embedding + probability field
- **Spatial system**: from pure 2D grid → dual-layer (physical geography + semantic narrative space)
- **State management**: from key-value vars → world memory graph (events, NPCs, locations as interconnected nodes with semantic embeddings)
- **LLM role**: from creation-time generation only → runtime interpretation of freeform commands + dynamic storylet adaptation
- **Frontend**: from Twine/.twee → purpose-built web UI (the API is the stable contract)

### New capabilities needed
- Embedding service (storylets, world state, player context → vectors)
- Semantic similarity / probability engine
- World memory graph (persistent, queryable, grows over time)
- Natural language command interpreter
- Runtime storylet generation (not just creation-time)

---

## Delivery Strategy

To deliver this vision without destabilizing the platform, execution follows a single roadmap in `improvements/ROADMAP.md` with two coordinated tracks:

1. Behavior-preserving architecture refactor (thin routers, shared service modules, stable API contracts).
2. Vision-driven capability milestones (world projection, grounded freeform actions, narrative beats, dual-layer navigation, runtime adaptation, and API-first client).

### Delivery guardrails

- Keep public routes and response shapes stable unless explicitly approved.
- Keep API modules focused on routing/validation and move business logic into services.
- Consolidate duplicated logic instead of parallel implementations.
- Gate each phase with passing tests (`python -m pytest -q`, plus targeted suite reruns as needed).

This keeps momentum on product vision while reducing structural risk and long-term maintenance cost.

---

## Relationship to Parallax

Parallax demonstrated how to embed concepts as vectors, compute typed relationships (causal, analogical, contradictory), use proximity as semantic relatedness, and visualize constellations of interconnected concepts. WorldWeaver applies the same principles to narrative:

| Parallax | WorldWeaver |
|----------|-------------|
| Terms (nodes in meaning-space) | Storylets (narrative nodes in meaning-space) |
| Probes (disciplinary lenses) | Story beats (narrative lenses on the world) |
| Semantic edges (typed relationships) | Narrative connections (causal, thematic, contradictory) |
| Centrality (importance weight) | Probability weight (likelihood of firing given context) |
| Convergent / Contradictory / Emergent | Expected events / Conflicting possibilities / Surprising emergent moments |
