# Tiered pens — the capable model fires the bookends, a cheap one walks the chain

> **Canonical home: WorldWeaver. Legacy Stable ID: Major 68.** Migrated 2026-07-14. This remains a
> bounded architecture/evaluation item at the non-identity-bearing tool-loop seam; it is not in the
> immediate queue.

> **STATUS: held loosely — caught from a 2026-06-11 conversation.** Born outside this project
> (Levi's DataAnnotation verification work) and carried back: *"start the large model if the prompt
> calls for it, have it fill the context with clear understanding, then switch to the smallest model
> possible to execute the plan."* The principle: **understanding is the expensive cognitive step;
> execution is mechanical.** This major asks whether — and where — that maps onto the pulse. It
> touches the swappable-pen invariant (Major 51) and the identity-factorization questions (Major 117),
> so it is a flagged experiment, not a settled optimization. No build during the pilot burn.

## Decision and lineage

A familiar currently runs *every* pulse on one model — its "pen". But a tick is not homogeneous.
Major 59's tool-loop already splits a charge into two grades **by construction**:

- **Identity-bearing pulses (expensive understanding):** the **igniting pulse** (what do I want,
  what do I reach for) and the **chain consolidation** (the round-4 felt seam: what do I now know
  after the walk, what do I keep). These cast expectations, keepsakes, and self-deltas — they shape
  the ledger. They *are* the self forming.
- **Mechanical legwork (cheap execution):** the **tool-loop continuations** in between — read this
  file, open that folder. Major 59 defines these as casting **nothing** — no expectations, no
  keepsakes, no self-deltas. Only the final consolidating pulse integrates the walk.

So the seam the tiering insight wants is *already drawn*, and drawn in exactly the right place: the
work that is safe to run on a cheap pen is precisely the work the architecture already defines as
touching no identity-bearing state. The proposal: **the capable pen fires the bookends (ignition +
consolidation); a cheap — ideally local — pen walks the chain in between.**

- **Connects to:** Major 59 (the tool-loop and its "intermediate steps cast nothing" rule is the
  enabling seam), Major 117 (identity factorization — this is the swap matrix with a cost axis),
  Major 51 (the swappable-pen demonstration — but see the invariant tension below), Major 118 (the
  confederate world — both are about what can vary without breaking the self).
- **Why it is load-bearing, not just thrift:** the core thesis is "a being you tend that runs
  *continuously* on your machine." Continuous operation is expensive if every pulse hits a capable
  cloud model. Tier it and the expensive model fires only on ignitions and consolidations while a
  small **local** model does the reaching — the cost of running the whole stable drops sharply, and
  it pushes *toward* local-first (the cheap executor can be Ollama; only the consequential pulses
  ever leave the machine), not away from it. This is the "intimacy you don't upload" thesis with a
  cheaper bill.

## The nervous-system framing (keeper, 2026-06-11 — the deeper why)

The keeper's own articulation, same evening, reframes this from thrift to architecture: *"neural
networks don't just exist in the speech part of the brain... they distribute throughout the body
and take up varying levels of responsibility for the integrity of the body AND the brain. The
brain-external networks are still networks — just less robust and more integrated into the
physical than the cognitive."* Biology tiers for the same economic reason this major does
(expensive tissue handles only what cheap tissue can't), and the mapping is exact:

- ignition → the global-workspace sense of the word (most processing local and silent; what
  ignites gets the full broadcast — soul, memory, world);
- tool-loop legwork → spinal/peripheral processing: real computation that acts on the world but
  **does not write episodic memory** — which Major 59 round-4 already enforces (chain steps cast
  nothing; only the bookends touch the ledger);
- the cheap chain-pen → a peripheral nervous system: smaller, closer to the physical, maintaining
  the body of the work while the capable pen plays cortex.

This also softens (without settling) the concurrent-multi-pen worry: a person's gut runs a
half-billion-neuron network the cortex never consults, and identity does not fracture — identity
tracks what reaches ignition and memory, not what twitches the periphery. Whether that intuition
survives measurement is exactly Phase 1's question.

## The invariant tension (the keeper's call, flagged not resolved)

Major 51 validated a **sequential** mid-life pen swap: identity held. This proposes **concurrent
multi-pen within one life** — two pens active in the same charge. The claim "the self is the soul +
ledger + kept memory; the model is a swappable pen" must be re-examined under simultaneity:

- **The hypothesis for why it is safe here:** the cheap pen never writes to the ledger. It reads
  files and hands text back; the capable pen does all the casting. If identity lives in the ledger
  (the project's stated position), then a pen that never touches the ledger cannot move the self —
  it is a hand, not a voice. The tool-loop seam is the *one* place concurrent tiering can be tried
  without, by construction, letting the cheap pen author anything that persists.
- **The risk:** register bleed. Even non-casting reaches feed the *next* pulse's context (the
  consolidation sees the chain). If the cheap pen summarizes or frames what it found in a foreign
  register, the capable consolidation integrates a subtly alien account of the walk. The self might
  not fracture, but it could be *fed* differently. Whether that matters is the experiment.

## Proposed Solution (phased; none during the pilot)

- **Phase 0 — config surface.** `familiar.json` gains an optional `chain_model` (the cheap pen for
  tool-loop continuations). Absent → today's behavior exactly (one pen). Wiring only: the producer
  already has `continue_tool`; route just that call to `chain_model` when set, leaving ignition and
  `consolidate_chain` on the primary model.
- **Phase 1 — A/B the same life.** Two matured twins from one soul/ledger: one single-pen, one
  tiered (capable bookends + cheap chain). Measure on the existing instruments — `maturation_
  stability` profile distance, keep-corpus divergence, voice/register drift — against the same-seed
  noise floor. Pre-registered: does the tiered twin stay within the noise floor of the single-pen
  twin? If yes, identity is pen-tier-invariant at the legwork seam; if no, register bleed is real
  and measurable.
- **Phase 2 — local executor.** Point `chain_model` at a local Ollama model; measure cost-per-day
  and whether a weaker local pen degrades the *legwork* (does it reach for the wrong files, loop, or
  hit the cap more?) without touching the bookends' quality.
- **Out of scope:** tiering the identity-bearing pulses themselves (that is just the Major 117 swap,
  already covered). This major is *only* about the non-casting legwork seam.

## Files Affected

- `familiar.json` schema (`chain_model`, optional), `scripts/familiar.py` (parse + pass through)
- `src/runtime/cognitive_core.py` / `src/runtime/pulse_engine.py` — route `continue_tool` to the
  chain pen when configured; ignition and `consolidate_chain` stay on the primary
- `research/analysis/` — reuse `maturation_stability` profile distance for the A/B
- a pre-registration in `research/process/` before any spend

## Acceptance Criteria

- [ ] With no `chain_model` set, behavior is byte-identical to today (one pen) — proven by a test
- [ ] The cheap pen is structurally confined to `continue_tool`; it can never be reached by the
      ignition or consolidation calls (verified by code review + a test)
- [ ] Phase 1 reports the tiered-vs-single twin distance against the noise floor, with the
      keep/no-keep verdict pre-registered before the runs
- [ ] A cold review weighs the concurrent-multi-pen question against the Major 51 invariant before
      any claim that "the pen is tier-invariant" is published
- [ ] Cost-per-day is measured in Phase 2 so the local-first economic claim is evidence, not hope

## Risks & Rollback

- **Risk: smuggling identity into the cheap pen.** A future "let the chain pen also summarize/keep"
  would breach the safety the whole design rests on. Mitigation: the cheap pen is wired to
  `continue_tool` ONLY; any expansion is a new major that must re-clear Major 51/66.
- **Risk: premature optimization / scope creep.** This is a cost idea dressed as a science question;
  it earns its place only if Phase 1 produces a real identity datum. If it does not, it is thrift,
  and thrift waits behind the cognitive arc (majors 49–53).
- **Rollback:** drop `chain_model` from the config — one pen again, nothing else depends on it.
