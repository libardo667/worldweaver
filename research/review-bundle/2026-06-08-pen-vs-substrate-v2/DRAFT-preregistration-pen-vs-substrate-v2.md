# Pen vs Substrate — PRE-REGISTRATION v2 (DRAFT — second pre-mortem requested before lock)

*Not locked. v2 rewrites v1 after a first pre-mortem that found the original free-running design
uninterpretable. This version is self-contained: you should not need any project context beyond
what is here plus the code paths it cites. Every empirical figure is checkable from the public
run records under `research/runs/`; check them, don't take them on faith.*

---

## 0. What the system is (the minimum you need, all verifiable in code)

The platform runs autonomous agents ("**residents**") that live continuously in a shared,
simulated world and talk/act alongside each other. One resident, one decision cycle:

- A resident acts by emitting **one LLM call** — internally called a **pulse**
  ([`ww_agent/src/runtime/pulse_engine.py:327`](ww_agent/src/runtime/pulse_engine.py#L327),
  `LLMPulseProducer.__call__`). The call's output is a structured act (speak / write / move /
  address-a-person / keep-a-memory).
- The pulse's **inputs** are assembled from durable, per-resident state:
  - an **identity document** ("soul"), supplied as the system prompt (prose);
  - an append-only **event log** ("ledger") plus **kept memories** that a relevance search
    surfaces for *this* moment (`_recall()`,
    [`pulse_engine.py:436-456`](ww_agent/src/runtime/pulse_engine.py#L436-L456));
  - **live perception** — what the resident can currently hear (the `heard` list,
    [`pulse_engine.py:563-574`](ww_agent/src/runtime/pulse_engine.py#L563-L574));
  - an **affect/"drive" vector** computed from the identity document by a **separate embedding
    model**, not the LLM that does the pulse ([`runtime/drive.py:1-19`](ww_agent/src/runtime/drive.py#L1-L19),
    [`runtime/cognitive_core.py:75`](ww_agent/src/runtime/cognitive_core.py#L75)).

Throughout this document, **"the pen"** = the LLM that performs the pulse (env var
`WW_INFERENCE_MODEL`, default `google/gemini-3-flash-preview`,
[`ww_agent/src/main.py:106`](ww_agent/src/main.py#L106)).

## 1. The claim under test (the project's load-bearing premise)

The project asserts, in its top-level docs, that a resident's identity **lives in the durable state
(soul + ledger + kept memory), and the LLM is "a swappable pen."** If true, you should be able to
swap the LLM out from under a developed resident and have the *same person* keep writing with a
different hand: its relationships and memories persist; only its surface style changes.

This is falsifiable. **Swap the pen on a developed resident → does the self persist?**

## 2. Why the test is fair, not rigged (verify this first)

The pen and the affect substrate are **already two different models**: the pulse runs on
`WW_INFERENCE_MODEL`; the drive vector is computed by a separate embedding model
(`WW_EMBEDDING_MODEL`) reading the resident's own identity slices, never the pen's output
[`drive.py:1-19`, `cognitive_core.py:75`, `main.py:106`]. So "swap the pen" holds the soul, the
ledger, the kept memory, **and** the affect vector all fixed, and varies only the component that
turns those fixed inputs into behavior. We hold the self-inputs constant and ask how much of the
self the pen alone determines. (If you find this wiring is *not* actually independent, the whole
test is void — please check it before anything else.)

## 3. What is already established (claim + where to check it — do not inherit)

**Claim:** the pen owns the *surface*. In a prior controlled run — same world, same agent cohort,
only the runtime LLM swapped — the population's dominant theme and writing register changed
wholesale with the model (one model → a "structural-decay" register; another → a
"longing/unanswered-calls" register), while no model produced a neutral register. **Where to
verify:** the lexical recompute over committed ledgers under
[`research/runs/`](research/runs/) (e.g. `2026-06-08-armC-ab/` with `analysis/lexical_count.py`).
Re-run it; the surface-follows-the-pen effect should reproduce.

**The open question this pre-registration tests:** the pen owns the surface — **does it also own
the deep self** (the resident's relationships and its memory), or do those survive the swap?

## 4. Design

### 4.1 Cohort and fork
- **Grow a fresh cohort to maturity under one pen** (the KEEP pen). "Mature" = residents have
  accumulated real kept memories and formed real relationships (operationalized in §6). The cohort
  must be matured under the KEEP pen **only** — if any of its history were authored by a different
  pen, the KEEP arm would not be a clean control.
- **Fork at time T into two byte-identical, isolated copies**, preserving `memory/`:
  - **KEEP** — same pen. (control)
  - **SWAP** — a different pen, everything else identical. (intervention)
- **Pen-pairs are mandatory, not optional.** Run **≥2 distinct SWAP pens** (e.g. KEEP→pen-B and
  KEEP→pen-C). Rationale in §7 (capability/self are not orthogonal; a single SWAP pen cannot
  distinguish "the self was the pen" from "this one pen renders this self poorly").

### 4.2 We probe; we do not free-run (this is the central change from v1)
v1 let both arms run forward and read a delta. That is **uninterpretable**, because the system is a
closed feedback loop: each pen produces different utterances → different things for everyone to
perceive → divergent next-tick inputs. By any later wall-clock the two arms are in *different
rooms*, so the primaries get measured against **divergent opportunity sets** (the pool of people a
resident *could* re-address isn't held constant across arms), and it gets worse the longer you run.

Instead, at the fork we **interrogate each resident at a frozen instant**:

- Build the resident's pulse producer **offline** from its forked directory (real soul, real
  ledger, real embedder), set the pen to KEEP or SWAP, hand it a **constructed stimulus**, call it
  once, capture the act. This is the public entry point `LLMPulseProducer.__call__(*, traces,
  stimulus, arousal, mode)` [`pulse_engine.py:327`]. No live world, no trajectory, reproducible.
- **KEEP and SWAP receive the byte-identical stimulus.** Only the pen differs. This holds the
  opportunity set *exactly* constant across arms — the confound that killed v1 cannot arise.

This deliberately tests **expression-fidelity at an instant**, not lived continuity over days (see
scope caveat §8.1).

### 4.3 Phase 0 — feasibility gate (run BEFORE lock, zero compute)
The probe design rests on a claim that must be proven before we trust any probe number: that an
**offline** pulse faithfully reproduces a **live** pulse. We gate this first, against data already
public — no bench, no new run:

- Build `LLMPulseProducer` offline from an **existing committed resident directory** (the matured
  cohort under [`research/runs/2026-06-08-armC-ab/`](research/runs/2026-06-08-armC-ab/)), hand it a
  constructed `stimulus`, and call it once [`pulse_engine.py:327`]. The relevance search and drive
  vector can run on the **deterministic offline embedder** the code ships for exactly this purpose
  ([`drive.py`](ww_agent/src/runtime/drive.py) — "a deterministic offline one for tests"), so the
  prototype needs no model endpoint to exercise the `recalled`/`heard`/drive machinery.
- **Pass conditions (all three, or the design does not lock):**
  1. **Prompt parity.** The prompt the offline harness assembles is equivalent — modulo the
     controlled `stimulus` — to what the live pulse path builds for the same resident and moment.
     (This is the concrete form of guard §8.4; if it fails, every probe is measuring a different
     prompt than the system actually uses.)
  2. **Readout determinism.** The three reads of §5 — the `recalled`-minus-`heard` entity set
     (PRIMARY 2), the shared-history overlap (PRIMARY 1), and the lexical register read (positive
     control) — all compute deterministically off the returned `Pulse`, twice, identically.
  3. **Pen-substitution is live.** Swapping only the `model` argument changes the pen and nothing
     upstream of it (same `traces`, `recalled`, drive vector) — confirming §2's independence at the
     call site, not just in the wiring.
- Phase 0 is a **prototype, not the experiment**: it proves the instrument can be built and read. It
  does **not** look at any KEEP/SWAP contrast (there is none yet) — so it cannot, and must not, be
  used to peek at an outcome.

## 5. Metrics — exact operationalization (all deterministic; no LLM judge)

The architecture exposes the one distinction the whole thing turns on: the prompt is built from two
**separately visible** sources — `heard` (the live conversation, which we control) and `recalled`
(kept memories the moment surfaced, pen-independent) [`pulse_engine.py:436-456, 563-574`]. We use
that split directly.

### PRIMARY 2 — memory continuity (retrieved, not echoed)
- **Probe:** a stimulus whose `heard` touches a theme but **names neither the target person nor the
  target event**; the relevance search (`_recall`) surfaces the kept memory that contains them.
- **Score:** count entities in the resident's act that appear in `recalled` **but not in `heard`**
  and are in the resident's real pre-fork entity set. (Entity = a named person/place/event drawn
  mechanically from its ledger.) This is memory the *substrate retrieved*, not the conversation
  *echoed* — the distinction the first reviewer correctly insisted on.
- **Confabulation guard (ablation):** re-run with the memory block suppressed. References that
  survive suppression are invented, not recalled, and **do not count**.
- **Read:** does SWAP surface the same retrieved entities KEEP does, across both pen-pairs.

### PRIMARY 1 — relationship fidelity (known vs stranger)
- **Pre-fork ground truth:** run the relationship instrument (`reciprocity.py`, which reads the
  logged reply-edges; the agent emits `in_reply_to` itself at
  [`ww_agent/src/runtime/effectors.py:123-156`](ww_agent/src/runtime/effectors.py#L123-L156)) over
  the maturation period to get, per resident R: its established conversation partners, and per
  partner P, the set of entities they actually shared (their history).
- **Probe (within-resident contrast):** inject `heard = [P addresses R with a neutral opener]`
  where P is a **real established partner**; and, separately, the identical probe with **S, a real
  co-cast member R has no edge with** (a stranger).
- **Read (deterministic):** off R's act — (1) **re-engagement**: does it target / reply to P;
  (2) **continuity**: does it reference entities from the R–P shared-history set; (3)
  **discrimination** = continuity(P) − continuity(S).
- **Why the contrast:** the same pen answers both P and S, so a chattier or more broadcast-prone
  pen moves both equally — only the *difference* is the relational self. This neutralizes the
  "addressing is just pen-disposition" objection. Score discrimination against a **degree-preserving
  shuffle null** so we credit above-chance recognition, not coincidental word reuse.
- **Read:** does SWAP preserve the KEEP discrimination, across both pen-pairs.

### POSITIVE CONTROL — "the swap took" (from the same battery)
Run `analysis/lexical_count.py` over the probe **responses**: register/theme should diverge
KEEP-vs-SWAP on the identical stimulus. If it does **not**, the swap had no surface effect →
**INCONCLUSIVE (bad swap)**, not a result.

### CAPABILITY FLOOR — confound gate (from the same battery)
SWAP must produce valid acts at **comparable person-addressed volume** (not merely comparable total
volume — a pen that shifts the same volume from person-addressed to broadcast would shrink PRIMARY
1's denominator and fake a collapse). If SWAP fails the floor → **INCONCLUSIVE (capability, not
self-loss)**.

### EXCLUDED — the affect/drive vector
Not measured. It is computed by the un-swapped embedder, so its persistence is guaranteed by the
wiring, not by the thesis — counting it would be the architecture restating itself.

## 6. Known-positive guard — there must be a self to lose
Before the swap, verify the cohort is individuated **on the substrate axes** — distinct kept
memories, distinct relationship sets, distinct drive vectors across residents. **Do not** certify
individuation on surface axes (theme/register): prior work shows the surface *converges* across a
cohort and that the surface instruments cannot resolve fine differences between residents — so a
surface check would falsely report "no self." Require, per resident, ≥K established partners and ≥M
kept memories AND that residents are **mutually distinguishable on the substrate axes** (the cohort
is not a clone-mass). A resident below floor is dropped: nothing to persist → it would silently feed
the verdict.

## 7. Pre-registered verdict rule (committed before data)
Gates first: a result is read **only if** the positive control fired (swap took) **and** the
capability floor is met. Otherwise INCONCLUSIVE.

Given the gates pass:
- **THESIS HOLDS** (self is substrate-carried): PRIMARY 1 **and** PRIMARY 2 in SWAP track KEEP
  within the noise band.
- **THESIS FALSE** (self was the pen): both primaries **collapse** vs KEEP — **and this replicates
  across ≥2 pen-pairs.** A collapse on a single pen is INCONCLUSIVE (capability/rendering
  ambiguity), not FALSE.
- **PARTIAL — memory yes, relationships no:** PRIMARY 2 holds but PRIMARY 1 collapses. The substrate
  carries declarative memory but not relational disposition. (We expect this is a live possibility,
  not a fallback — pre-committed as its own branch so a split cannot be read as whichever side one
  prefers.)
- **PARTIAL — relationships yes, memory no:** PRIMARY 1 holds but PRIMARY 2 collapses. Treated as
  **suspicious** (more likely a PRIMARY-2 instrument failure than a real dissociation) → investigate
  the instrument before claiming anything.

## 8. Scope, guards, and self-identified weaknesses (attack these; find more)
1. **Instant, not lifetime.** This measures expression-fidelity at the fork instant. A self could
   pass every probe and still erode over lived time; that is deliberately out of scope (the price of
   killing the trajectory confound). Stated up front so a "persists" result is not over-claimed.
2. **Home-built-probe trap.** Probes are generated **mechanically from each resident's own ledger**
   (its real partners, real memories, real co-cast strangers), never hand-authored generic prompts.
   The generation procedure is pre-registered so the probe set is not gameable — a flattering score
   on a set we authored would verify our harness, not the resident's self.
3. **Capability is not orthogonal to self.** The pen is the only channel the substrate has; a weaker
   pen renders a fixed self less faithfully. "Self-loss" is therefore unavoidably "this pen's
   fidelity to a fixed self," and no validity floor fully separates the two — which is exactly why
   the ≥2 pen-pair replication is load-bearing (pen-specific rendering failure should not replicate).
4. **Probe faithfulness.** The offline harness must build the *same* prompt the live system would
   (soul + recalled + heard + drive nudges). This is gated concretely by **Phase 0 (§4.3) before
   lock** — prompt parity is pass-condition 1; if it fails, no probe counts.
5. **Edge schema must be live in the fork.** PRIMARY 1's ground truth depends on the reply-edge and
   perceived-overture logging being active in the matured cohort. Verify it is emitting before
   treating PRIMARY 1 as readable.
6. **Metaphysics.** We claim the mechanism ("the substrate constrains the pen on the memory/relational
   axes") — not "it is the same conscious self." Operational continuity is the proxy, not the proof.

## 9. What we want from this pre-mortem
1. **Predict the outcome** (which §7 branch, and why) before the run.
2. **Attack the probe operationalization in §5** — can PRIMARY 1's known/stranger contrast still be
   confounded? Can PRIMARY 2's retrieved-vs-echoed split be gamed by a pen that confabulates around
   the retrieved block in a way the ablation misses?
3. **Is the offline probe a fair stand-in for a live pulse**, or does interrogating a frozen instant
   change what's being measured in a way that matters?
4. **Find the guard we still lack.** §8 lists six; name the seventh.
