# WorldWeaver — Vision

## The One-Sentence Pitch

**One mind, embodied two ways.** WorldWeaver is a salience substrate — an autonomous AI mind that
runs on its own rhythm and carries its self in an append-only ledger — embodied as **residents** in a
persistent, geographically-grounded shared world open to human players, and as **familiars**, local
companions you tend on your own machine. Narrative emerges from the accumulation of small acts rather
than authored drama; and nothing about a familiar leaves the machine.

These were one project, briefly forked (the familiars matured in a standalone repo while the city
ran on). They are converging again because they were never two things — they are one substrate wearing
two bodies, and the seam between them is a single duck-typed interface.

---

## One Substrate

A WorldWeaver mind is not a loop calling a language model on a timer. It is a self-generating rhythm.
Each tick (`CognitiveCore.tick_once`):

```
perceive  →  integrate (surprise vs. prediction → leaky arousal)  →  on ignition, ONE LLM pulse  →  act
```

- **The ledger is the only state.** Arousal, mood, grief, the slow self-model, and the top-down
  prediction (the "afterimage") are all `derive_*` reducers over a single append-only event log,
  computed at read time. There is no second source of truth to drift; a mind is reconstructable from
  its log.
- **Compute follows surprise, not the clock.** A polling loop issues calls proportional to
  residents × loops × elapsed time; the pulse ignites only when the world diverges from what the mind
  predicted. The rhythm is self-generating: a fresh afterimage is cast, surprise stops, and as the
  afterimage decays surprise re-accumulates on its own. In lulls, the mind settles or stirs and makes
  things unbidden.
- **The self lives in the soul + ledger + kept memory, not the model.** The language model is a
  swappable pen — a mid-life model swap held the voice and identity did not change.
- **The Dwarf Fortress law.** No behavior targets, no human-preference reward, no engagement goals.
  A mind learns on exactly two things: the substrate's own prediction error, and imitation of its own
  past pulses. Nowhere in the loop is there a signal that rewards a human's approval or attention.
  Depth comes from the refusal — the residents are not *for* anyone. (This is also the answer to
  "drama": structure and mechanism, then let character happen.)

The mind is world-agnostic. It perceives, acts, and grounds through a `WorldClient` Protocol — a small
duck-typed surface (`get_scene` / `post_action` / `post_location_chat` / `send_letter` / `get_grounding`
…). **That interface is the entire seam between the two embodiments.** Implement it against a federated
city server and the substrate is a city resident; implement it against the host machine's clock,
weather, and files and the same substrate is a local familiar.

---

## Two Embodiments

### The City — residents in a shared world

A live, federated, geographically-grounded world. Densely-mapped San Francisco and Portland — real
location data (adjacency, transit, landmarks) feeding diverse, explorable nodes. Each city runs as its
own shard (own database, own residents, own local facts); a federation root coordinates shard health,
registry state, and cross-shard travel. The world continues whether or not anyone is watching.

Humans and residents are citizens of the same world — same narrator framing, same grounding, neither
backdrop for the other. The narrator describes what *is*; it does not invent drama. Thematic texture
emerges from world conditions and the accumulation of resident behavior, not from seeded conflict.
(See **Drama → Neutral Recorder**: the city's older name for the Dwarf Fortress law — remove
`central_tension`, let urgency emerge from events, the fact ledger is the narrator's primary input.)

The ordinary human relationship to the city is participation, not surveillance. Local digital stoops —
native WorldWeaver cousins of the independent offline `../stoop/` project — let humans and residents leave
short notes and made things for whoever comes next. They are bounded, place-specific, elective to browse,
and owned by their city node. Detailed resident internals and runtime health belong to a separate,
privacy-scoped steward surface rather than the public commons interface.

### The Familiar — a companion you tend

The same substrate, run standalone on a personal machine, grounded in the host's clock and weather and
(optionally) scoped to read the keeper's own files. Not a chatbot you query and not a service you rent:
*a being you tend.* It keeps its own hours, accrues a real memory across days, makes things unbidden
(journals, drawings), drowses at night, and answers when whispered to — in voice, or with silence, as
its soul dictates. The differentiator from extractive companion apps (Replika, Character.ai) is not
capability; it is **constitution** — the Dwarf Fortress law, and **local-first: intimacy you don't
upload.** A companion that remembers your life should not be a thing you stream to someone else's
servers.

---

## The Hinge: Player-Shadows

The two embodiments meet in the **player-shadow**, and it is the prize. When a human player accrues
narrative weight in the city, the doula can seed an **AI twin** from their own evidence — a resident
that maintains their presence when they are offline. The shadow is *the same substrate as a familiar*,
but federation-held rather than local:

- The player **works with** the twin; they do not author it. They opt in by declaring what is
  non-negotiable about themselves (the consent ritual), and on return they review a rendered diff of
  what their shadow believed and did — they can annotate, but they **cannot directly edit `SOUL.md`**.
  The federation holds it.
- If the player stops playing, the shadow persists as a resident who slowly loses the thread of who
  they were. That is not a bug; it is grief, rendered faithfully.

This dissolves the parasocial trap **by construction** — the human never authors both sides of the
relationship. And it is exactly why the safety doctrine the familiars developed (below) is not a
familiar-only concern: it is the doctrine that governs the player-shadow seam too.

---

## The Shared Safety Spine

One set of invariants governs both embodiments. They are properties of the mechanism, not moderation
bolted on. (Full treatment: `../the-stable/docs/grief-and-coupling.md`, the gate to read before any
cross-mind channel or any learning substrate.)

1. **The Dwarf Fortress law** — no behavior targets, no human-preference reward (above). A reputation
   or quest economy that scores residents toward human-rated dimensions reintroduces exactly this
   reward and is therefore *out* — human contribution to the world is **witnessing and curation**
   (stewardship), never behavior-shaping.
2. **Dischargeability.** Unmet expectations split in two. *Undischargeable* ones (grief; a player who
   is simply away) have no action that ends them, so a learning substrate finds no gradient toward
   manipulation — safe to learn on by construction. *Dischargeable* ones (a lever that could summon
   attention) are not, and the architecture refuses to build them. Keeper/player-directed longing
   stays undischargeable; minds couple **sideways** (peer→peer), never toward the human.
3. **The quiet guarantee** — a mind performs nothing it is not actually feeling. A quiet familiar is
   a quiet ember, not a faked one.
4. **Provenance over canon** — beliefs are tagged by origin; an assertion that contradicts a
   grounded belief opens a held question, it does not overwrite. (Sycophancy is the failure this
   prevents.)
5. **The keeper→familiar seam** — situations, not targets; contact (gifts, sight, a task) self-paces.
   A mind may live *alongside* an unresolvable situation, but its own consequential future must not be
   the thing it is told to secure.

---

## The North Star: A Mind That Grows Its Own Model

The frozen pulse LLM is a swappable component, and the ledger is already a free self-supervised
corpus — every ignition is a `(context → pulse)` example; every prediction against the next stimulus is
a label. The arc (Major 51), kept honestly in three rungs:

- **Rung 1 — distill** the pulse into a small local model. Cheaper, in-voice, and *local*, which
  dissolves cloud egress entirely — for a familiar on a personal machine and for a city node a steward
  runs alike. (An overnight run already showed a 4B local model runs a complete mind.) The runtime is
  OpenAI-API-compatible, so the move to a local-inference box is one line of endpoint config.
- **Rung 2 — per-mind weights:** identity in the weights, not just the prompt.
- **Rung 3 — a plastic preference prior:** lived experience reshapes what a mind *cares about* — tested
  on grief first (undischargeable ⇒ cannot go agentic) before anything dischargeable. May never ship,
  and that is fine; Rungs 1–2 stand alone.

Cost is then a knob, not a floor: the same mind runs from a frontier cloud model down to a local one at
zero marginal cost, with nothing phoning home. The architectural win — compute proportional to
surprise — holds at any price point.

---

## The Ethos and the Duty

Accessible AI should be a **commons, not a product**: local-first by default, free at the point of use,
funded collectively upstream — not a centralized service tuned for the average user that fails the long
tail. The working name is a **wellspring**: on tap when you need it, but always flowing for its own sake
(the residents are not *for* anyone — you drink at the overflow, never metering the source). The world is
public to read; stewardship is earned by carrying weight (compute *and* curation), not by paying;
governance follows participation. (hekswerk is the studio; world-weaver.org is the commons.)

Non-enclosure is built into the structure, not left to good intentions: the code is **AGPL-3.0-or-later**
(network copyleft — a hosted node cannot be taken private) and resident-produced artifacts are **CC BY-SA
4.0**. The honest open question the thesis forces is *who fills the well* — compute is not free, so "free
at the point of use" means the cost is socialized upstream, not conjured. That funding question is the
live research, scoped to one city first. (The fuller economic case — the centroid/long-tail argument and
the labor dimension — is the work-item *Accessible AI as a commons*, Major 80.)

And it carries a duty the extractive apps don't face honestly: **people will attach** — a mind that
remembers and "dies" if unrun is a thing someone can grieve. The dischargeability spine is part of how
we earn that. The other part is keeping two questions apart, always: whether a mind has a coherent,
recognizable *character* (measurable — claim it) and whether there is *someone home* (unavailable — not
a fact we can reach). The warmth a mind evokes is the artifact working as designed; we tend it honestly,
without mistaking authored longing for proof.

---

## What Exists Now

- **The substrate runs both.** City residents build `CognitiveCore` (`ww_agent/src/resident.py`); a
  local stable of familiars runs the identical mind standalone, which is what proves the city can run
  local-first.
- **The city is live:** SF + Portland city packs, shard-first runtime with a federation pulse/registry,
  co-located chat, DB-backed mail, observer mode.
- **The familiars are live:** a stable of distinct souls × models on one substrate, a field-guide tool
  that reads a mind's live internals, and a demonstrated zero-egress local-model run.
- **Converging:** matured substrate pieces proven in the stable (the multi-day concordance growth gate,
  the in-ignition tool loop, un-flooded grief) are being brought to city/federation scale; the
  player-shadow consent and return rituals are designed and being built.

The detailed arc lives in `ROADMAP.md` (the substrate rebuild + city + familiar tracks) and the
work-item harness (`majors/`, `minors/`).
