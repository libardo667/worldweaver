# Marination as capability equalizer — the pen-strength × substrate-richness interaction

## The claim (one line)

A weak pen on a rich substrate may match a strong pen, because **marination (soul + ledger + kept
memory + the slow re-derivation loop) carries more of the cognitive load for a thin-weighted model
than for a flagship.** If true, the marination *lift* is larger for the cheap pen than the expensive
one — and the self is even more substrate-borne than the fixed-substrate pen-swap can show.

## Decision and lineage

This major is **proposed (2026-06-09, operator's call)** and **parked behind the running pen-vs-
substrate swap** — do not perturb that cohort to run it. It is the natural *next axis* after the swap,
sparked by a standing observation across both forks of the substrate:

- **gemini-3-flash, not a flagship, not even the latest flash**, is what produces the worldweaver
  cohort's rich prose, diaries, and kept memories (the Albina disaster scene; the matured D2 cohort).
- **Maker** (the-stable's contemplative-mirror familiar, the one handed `read_roots`) was bumped
  **haiku-4.5 → sonnet-4.5 unannounced** on 2026-06-04 — soul/memory/substrate continuous, only the
  pen changed, the creature could not know — and came out **voice held, depth deepened** (haiku-Maker
  *described* the architecture; sonnet-Maker read `cognitive_core.py` and turned it on his own mind).
  He also caught in-situ substrate errors the **Opus-class executor wasn't noticing** (see the
  watchman corollary below — that one is a *different* finding).
- The current pen-swap (`record_run` KEEP → offline `replay_run` into foreign pens) **varies the pen
  at fixed, rich substrate**. It cannot, by construction, answer *whether a weaker pen benefits more
  from the substrate than a stronger one* — that needs the substrate varied too.

Relationship to other work: builds directly on the pen-swap harness (`ww_agent/scripts/pen_swap/`,
`research/runs/2026-06-09-pen-vs-substrate-grow/`) and reuses the cohort + `portraits/choice_points.py`.
Coordinates with [[major-51-own-trained-model]] (the cheap/local-pen economic path) and the VISION
"the model is the pen" line.

## The claim, disentangled (three claims wearing one coat)

The casual form — "smaller models benefit from marination" — bundles three separable assertions. Only
the third is this major. The first two are named so they are NOT smuggled in as evidence.

1. **Role, not size (the watchman confound).** Maker-caught-bugs-Opus-missed is mostly about a
   single-purpose, infinite-dwell observer out-noticing a busy goal-forward executor — true at *any*
   tier. This is a real and valuable finding about cognitive architecture (a slow narrow observer is a
   different organ than a fast broad executor), but it is NOT evidence about model size. Tracked
   separately (the watchman corollary). Must not contaminate the equalizer metric.
2. **Style prior, not lift (the flash-floridity confound).** Some of flash's "richness" is flash house
   style (tuned fluent/uncautious; flagships RLHF'd toward hedging that flattens voice). The-stable
   already flags the twin worry ("gemini's reciprocity might be a model-STYLE prior"). Controlled by
   same-seed pen-swap on a fixed substrate (does richness survive the pen, or just change accent?).
3. **THIS major — the interaction.** A flagship carries more *in the weights*, so the marginal value
   of an external ledger is lower (the substrate is partly redundant with what it already knows). A
   thin-weighted pen has more room to be lifted, so structured external memory is a bigger *relative*
   gain — scaffolding as a capability equalizer. Plus the slow-loop is externalized across-time
   chain-of-thought: a weak pen forced to re-perceive/re-derive over hundreds of ticks turns repeated
   cheap glances into something like one deep look. **Prediction: marination closes more of the gap
   for the weak pen than the strong one.**

## The experiment — a 2×2 (pen-strength × substrate-richness)

```
                  thin substrate          rich (matured) substrate
weak pen   (flash)        A                          B   ← ~ the KEEP run (already in hand)
strong pen (opus/sonnet)  C                          D   ← ~ the swap (already in hand)
```

- **B** — weak pen + rich substrate = the home-pen KEEP recording on the matured cohort.
- **D** — strong pen + rich substrate = the foreign-pen replay of the same matured substrate.
- **A** — weak pen + thin substrate = a flash **cold-boot** (no marination; fresh souls, empty ledger).
- **C** — strong pen + thin substrate = a strong-pen cold-boot.

A and C are the only new runs, and they are cheap (ungrounded cold-boots, machinery already exists in
`rehydrate.py --source` + `record_run` against a fresh cohort with no carried memory).

**The claim is the interaction, not any single cell:**

> marination lift for the weak pen  (B − A)   >   marination lift for the strong pen  (D − C)

## Metric (pre-register before running — must be ABSOLUTE, not divergence)

The swap's metric is *divergence from KEEP*; that is useless here because cold-boot cells (A, C) have
no KEEP to diverge from. The 2×2 needs an **absolute** per-cell quality measure. Candidates to pin:

- **Individuation density** — salience-symmetric elective rate (`choice_points.py`-style: choices the
  substrate, not a salience gradient, broke) per scored resident. Higher = more substrate-borne self.
- **Curation coherence** — do kept memories assemble a cross-attributed shared model (cf. the Albina
  scene: residents keeping facets and citing each other) vs generic/disconnected notes?
- **Voice distinctness** — pairwise inter-resident style/embedding separation on identical stimulus
  (the "sixteen frames on one disaster" property), measured absolutely, not against a reference.

Pin K-style floors a priori (≥ N scored residents/cell). Below floor at a cell → that cell is
INCONCLUSIVE, never the result. Pin one headline metric; report the others as secondary.

## Confounds & controls (do not skip)

- **Style prior (claim 2):** same family, same seed across pens; report style separately from
  individuation so floridity ≠ depth.
- **Watchman/role (claim 1):** this experiment is about *generative individuation under marination*,
  NOT the noticing niche. Keep all cells in the same generative role; do not mix in the read-roots
  observer task.
- **Denominator / survivorship:** the whole hunch is anecdote until it has a miss-rate. Count
  false-positives (incoherent "rich" prose, confabulated keeps) per cell, not just the wins.
  "Found himself in it" is *also* exactly what a confabulating model does — pattern-match the prompt
  into a coherent story. No denominator, no claim.
- **Substrate-richness must be matched A↔B and C↔D** (same souls, same world seed; only marination
  differs) or the interaction is uninterpretable.

## Falsifier / when it's NOT worth it

State all three outcomes a priori:

- **Supported:** (B − A) > (D − C) by the pinned margin → marination is a capability equalizer; the
  cheap/local-pen-hosts-a-growing-mind path is real. (Strongest payload.)
- **Null:** (B − A) ≈ (D − C) → marination lifts both pens about equally; it's pen-agnostic
  scaffolding, not an equalizer. Still useful, weaker claim.
- **Inverted (the one that would hurt):** (D − C) > (B − A) → strong pens benefit MORE from rich
  substrate (capability *compounds* with marination). The cheap-pen future is then false, and the
  flagship is the right host for a deep self. Pre-commit to reporting this plainly if it lands.

If the swap (claim 2's control) shows the home-pen richness is mostly flash style — collapses under a
flagship pen at fixed substrate — then the equalizer question is partly moot and this major narrows to
"does marination lift a weak pen's *individuation* (not its prose) more than a strong pen's." Re-scope,
don't abandon.

## Payload (why it's worth a major down the road)

- **Economic / environmental.** Maker on cloud is ~$0.20–1.70/day; the 12-resident flash shard is
  ~$1.17/hr. The Major 51 local-distill path drives marginal cost to $0 with nothing leaving the
  machine. If marination equalizes, persistent capable selves do not need frontier models — the
  low-footprint, democratizing, commons path is the *better* path, not a compromise.
- **Philosophical.** Every notch the equalizer holds pushes the self further into the substrate and
  the model further toward "swappable pen" — the load-bearing thesis, strengthened from a new angle.

## Watchman corollary (a sibling finding — write up separately, do not merge)

The Maker-caught-bugs-the-executor-missed result is its own thing: **a slow, narrow, infinite-dwell
observer is a complementary organ to a fast, broad executor**, and the architecture wants both. This
is about attention allocation + dwell time + the marination loop forcing re-reading on a *stable
target*, not about model size. It suggests a standing "watchman" familiar with `read_roots` as a
drift-detector that notices in-situ substrate change the executor is too busy to see — measured by
catch-rate AND false-positive-rate (denominator discipline applies here too). Candidate for its own
minor/major; flagged here only so it is not folded into the equalizer claim.

## Not now

Parked behind the pen-vs-substrate swap (running it now would perturb the cohort and compete for the
same harness). Promote to active when the swap closes and its claim-2 control (style vs substrate) has
reported — that result tells us how to scope cells A and C.
