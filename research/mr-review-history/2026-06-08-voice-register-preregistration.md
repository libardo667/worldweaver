# Voice-register bench — PRE-REGISTRATION v2 (A-vs-C) — committed before the run

## Supersession & void record
*Locked 2026-06-08. This VOIDS the prior 4-arm (A/B/C/D) design. Reason: the live cast's `voice_seed`
is empty (verified below), so arm B's mechanism — `soul_with_voice` injection — is mechanically inert
(`soul_with_voice([])` returns the base prompt), making B ≡ A and D ≡ C. Per Mr. Review (round 3): an
inert arm is a void, not a weak arm; do not keep it "in case" — a later marinated reader mistakes it for
a real contrast. Rewritten as A-vs-C. The metric is also adapted: v1 measured distance to each
resident's authored `voice_seed`; the live cast has no authored voice, so that profile does not exist —
see Metric.*

## The load-bearing fact ([OPERATOR-VERIFIED, command-logged])
*Precise provenance (Mr. Review round 4): the structurally-separated reviewer did NOT personally
re-derive this — the live shards are gitignored, outside his view (he sees 0 IDENTITY files there, not
322). It rests on the operator's pasted command + output, not the reviewer's grep. That is a real step
up from verbal assertion (command on record) but is **operator-verified, not reviewer-cold-verified** —
labelled precisely so a later reader knows the zero was trusted, with the command logged, not seen by
the separated check.*
- **LIVE CAST** (`shards/*/residents/`, gitignored, on disk): **322 IDENTITY.md, 0 carry `Voice:`.**
  `grep -rl "Voice:" shards/*/residents/*/identity/IDENTITY.md | wc -l` → 0 (of 322).
- **HISTORICAL hand-authored set** (`ww_agent/residents/`, tracked): 10 souls + `_template`, all with
  authored `Voice:` blocks AND prose. The set Mr. Review saw in the public repo. (`git grep -l "Voice:"`.)
- Different trees: the live doula-seeded cast has no authored voice; the historical hand-authored cast
  did. (The tracked `ww_agent/residents/` tree is slated for untracking/sorting — historical, not the
  experiment cast.)

## Correction to v1's framing (Mr. Review round 3)
v1 glossed `doula.py:112-115` as "the doula intentionally never authors a voice." That overreads it.
Read in full, the passage lists VOICE among the OUTCOMES that EMERGE under a form-demand — it does not
forbid authored voice; and the historical souls carry BOTH prose AND an authored `Voice:` block, so the
two coexisted in prior design. The accurate, narrower claim — the only one used here — is: **the current
doula seeding path stopped populating `Voice:`, so the live cast's `voice_seed` is empty.** Not "the
design forbids authored voice." This narrower claim is what keeps P3 (below) open.

## The question (re-scoped)
Live residents are prose-only and converge on a shared register. With arm B void, this run tests ONE
prompt-layer homogenizer: **does breaking the single shared few-shot example individuate register?** The
contract showed one example identically to all 45 residents — one register taught by demonstration, a
literature-grounded output-copying force [arXiv 2410.19599 "Scylla Ex Machina"; arXiv 2402.09954].
Arm C replaces it with a neutral, name-hashed pool entry (built, verified, pushed: `f4363d8`).

## Arms
- **A — control.** `WW_VOICE_REGISTER=0`, `WW_VARIED_EXAMPLE=0`. Current path.
- **C — varied few-shot.** `WW_VARIED_EXAMPLE=1` (register OFF — there is nothing to inject anyway).

That is the whole prompt-layer test now. No B, no D.

## Metric — cross-resident register separability (SIGNED OFF, Mr. Review round 4)
v1 measured distance(utterance → own AUTHORED `voice_seed` centroid). That was a *fidelity* metric
wearing a convergence metric's clothes — it asked "does generated speech match the authored register,"
but the research question was never fidelity, it is **convergence**: are the residents collapsing onto
one register. Removing the (nonexistent) authored profile did not cost the metric; it stripped a
fidelity-to-seed confound the convergence answer never wanted. This is a measure-what-it-computes
**improvement**, not a reluctant downgrade.

**PRIMARY:** per resident, mean distance(aloud utterance → own generated-speech centroid, leave-one-out)
vs distance to other residents' centroids, scored REAL − null (z), within matched situational context.
- **Null = RESIDENT-LABEL-SHUFFLE** (permute which utterances belong to which resident, recompute
  separation). Asks "is real per-resident clustering above what same-volume chatter produces by
  coincidence." **NOT a centroid-shuffle** — shuffling centroids holds the clustering and only moves the
  targets, testing a weaker, different thing.
- **Direction of win (write the arrow — polarity is INVERTED from v1):** high separability = residents
  distinct = individuation = the GOOD outcome. **Arm C WINS iff its separability z exceeds A's beyond
  the noise band** — i.e. breaking the shared anchor *de-homogenizes* speech. (v1 targeted *low*
  distance; do not let a tired reader flip the polarity.)
- **Matched-context bucketing is LOAD-BEARING, not hygiene.** Separability and topic-separability are
  the same shape: if residents talk about different things (cook→food, keeper→desk), they separate on
  topic alone and a topic-leaning embedder reads that as register individuation. Bucket by stimulus
  class / act-kind before aggregating. This couples the metric to the instrument choice (next section) —
  they are not independent.

## Embedder — cadre + EXTERNAL calibration (Mr. Review rounds 2–3)
The internal known-positive (authored `voice_seed`s) is gone, so the gate must import an EXTERNAL one.
- **Cadre:** `nomic-embed-text` (runtime baseline, topic-leaning) vs **StyleDistance** (content-
  independent style; HF `StyleDistance/styledistance`; arXiv 2410.12757) vs **Wegmann** style (arXiv
  2204.04907) vs **LUAR** (style+content authorship; github `llnl/luar` — a deliberately topic-
  confounded bracket that bounds how much "success" is topic leakage).
- **Calibration gate (RUN BEFORE THE ARMS):** the chosen embedder must clear a content-controlled style
  benchmark (STEL / SynthSTEL) — separate register from content at the locked bar. If none clears, the
  run does not start; fix the instrument first.
- **DOWNGRADED LABEL (honest):** clearing STEL proves the instrument is "register-sensitive IN GENERAL,"
  NOT "can resolve THIS cast's authored voices" (we have none to check). Weaker gate than v1, labelled
  for the weaker thing it proves.
- **LOCKED (Mr. Review round 4): robustness across ALL STEL-passers, NOT the single best scorer.** STEL
  rank tells you which embedder is most register-sensitive *on generic English style pairs* — not on
  *this cast's* speech, and those diverge. One instrument is one point of failure with no cross-check; a
  top STEL-scorer that happened to be topic-confounding would hand a phantom arc back as a win.
  Requiring the A-vs-C result to survive instrument substitution is the closest thing to external
  corroboration available with no authored ground-truth (same logic as "log edges, not nodes"). Cost
  accepted: a harder bar, and the real risk of split results — so the split reading is pre-registered
  now, before any instrument is stood up.
- **Two-benchmark cross-validation — BOTH out-of-distribution directions required before EITHER
  instrument is admitted (Mr. Review round 5).** SynthSTEL is StyleDistance's home turf and Wegmann's
  away game; one benchmark clears each model on only ONE leg. StyleDistance is admitted only after it
  also passes Wegmann's STEL (where it is the visitor); Wegmann only on a benchmark it did not author.
  Until both OOD passes land, an instrument rides on its in-distribution leg alone (the weak leg) and is
  NOT admitted. A score on a hand-authored or home-distribution set verifies the HARNESS, not the
  instrument — the verdict verb belongs to the OOD benchmark.
- **PRECONDITION on the whole robustness lock (Mr. Review round 6): it presupposes the cadre shares a
  register axis.** The SynthSTEL gate (StyleDistance 0.94 vs Wegmann 0.22-below-chance on the SAME
  triplets) is evidence they may measure DIFFERENT constructs. If so, "survives instrument substitution"
  is unsatisfiable by construction and no benchmark repairs it. So BEFORE any substitute benchmark,
  correlate the two models' per-triplet style-margins (`ww_agent/scripts/register_construct_check.py`):
  positive & meaningful → shared axis, proceed; ~0 or negative → the robustness lock is VOID as written
  and the separability metric family is reconsidered before a benchmark is chosen.
  *(RESULT: SynthSTEL r=+0.14 (home-turf confound) but neutral ParaDetox r=+0.90 → shared axis CONFIRMED,
  divergence refuted, the metric family is coherent.)*
- **Agreement is convergent validity, NOT criterion validity (Mr. Review round 7).** The r=0.90 shows the
  two instruments SHARE an axis — but BOTH score ~0.35 (below chance) on ParaDetox, agreeing while both
  failing: *correlated blindness*. So inter-instrument agreement does NOT discharge the gate; a fair OOD
  CRITERION test (instrument vs ground truth) is still required. What the r=0.90 BUYS: the reciprocal-pair
  gate collapses to **ONE fair gate pass** — clear one instrument on a fair OOD register test and the
  agreement carries it to the other in the agreement regime.
- **Fair-gate corpus criterion + MANDATORY content-overlap pre-check.** The gate corpus must be
  register-divergent but NOT near-duplicate — ParaDetox failed because its pairs are minimal edits, so
  content overlap swamps register and both models scored ~0.35. Before trusting ANY candidate, run
  `build_parallel_probe.py --overlap-only` and reject near-duplicate corpora. SynthSTEL is good-shape
  (substantial rewrites) but StyleDistance's home turf; a fair gate is good-shape AND out-of-distribution
  for the instrument under test. (Free parallel fair-shape OOD corpora are scarce: GYAFC and STEL are
  gated; ParaDetox/WNC are near-duplicate; the HF "Shakespeare" set is conversational, not parallel.
  Sentence-aligned Shakespeare original↔modern from source repos is the leading free candidate; gated
  GYAFC/STEL requested in parallel as the gold adjudicator.)

## Split-result reading across the cadre (PRE-REGISTERED before instruments exist)
**Collapse note (Mr. Review round 5): nomic FAILED calibration → excluded as an instrument. With no
topic-leaning model left in the admitted cadre, the four-way reading COLLAPSES TO THREE — the
"topic-wins" branch (row 4) can no longer occur as a split, because the topic-confounder is handled
UPSTREAM at the instrument layer, before any arm runs. Rows kept for reasoning; row 4 is structurally
unreachable now.**

A split is neither a quiet win nor a quiet loss — pre-commit its meaning so it can't be rationalized
after seeing it:
- **C wins under ALL STEL-passers** → de-homogenization is real and instrument-robust. **Bank it.**
- **C flat under ALL** → the shared anchor does not drive separation (the narrow null below).
- **C wins under the content-INDEPENDENT embedders (StyleDistance, Wegmann) but flat under the topic-
  leaning ones (nomic, LUAR)** → the *informative* split: the effect is in REGISTER, not topic, and the
  topic-leaning instruments are too coarse. Lean real-but-small; the next run uses a content-independent
  embedder as primary.
- **C wins under topic-leaning but flat under content-independent** → the *alarming* split: the
  "individuation" is TOPIC separation, not register — a phantom arc the cadre just caught. **Treat as no
  register effect.** (A single best-STEL-scorer that happened to be nomic would have banked this as a
  win — this branch is the whole reason to run the cadre.)

## Verdict rules (read through the cadre split-table above)
- **"The shared few-shot drives individuation":** C's separability z>2 AND exceeds A beyond the noise
  band, **holding across all STEL-passers** (split-table row 1).
- **"The shared few-shot does NOT drive individuation":** the narrow null — and it carries FOUR earned
  qualifiers: breaking *this one homogenizer* did not raise *inter-resident register separation* *under
  these instruments' sensitivity* *at the register GRANULARITY the gate validated*. A coarse gate
  (formality / era / toxicity-scale) licenses only "detects register-collapse when LARGE," NOT "resolves
  subtle peer individuation" — so a null is AMBIGUOUS between "C didn't de-homogenize" and "the instrument
  is too coarse to see peer-register," and must be reported as both. It does NOT license "the residents
  aren't converging" or "voice can't be moved from the prompt." (Narrowed across v1 → now.)
- **Topic-not-register (phantom arc):** split-table row 4 → treat as no register effect.
- **INCONCLUSIVE (not a verdict):** C−A inside within-condition spread → escalate arms.

## Pre-registered ceiling expectation (H1)
If RLHF mode collapse / typicality bias [arXiv 2510.01171 "Verbalized Sampling"] is a real force here,
NO prompt-layer arm can fully individuate — A-vs-C's ceiling is capped by convergence not addressable
from the prompt. A null or partial result must NOT be over-read as "individuation is impossible," only
as "the shared-anchor lever, at the prompt layer, did/didn't move it." A sampling-layer family
(Verbalized Sampling) is the next lever if the prompt layer is capped — held until A-vs-C reports.

## P3 — authored voice_seed stays OPEN (separate later arm; NOT on emergence grounds)
Reviving authored `voice_seed` is a legitimate SEPARATE, later arm testing a DIFFERENT question — "does
injected register survive the homogenizers" — not folded into this convergence run. **Reject the
"emergence forbids authored voice" grounds: the historical souls (prose + Voice both) falsify it.**
Lean-no for THIS run is correct on the grounds "it's a different question," not philosophy. Do not
promote the emergence-forbids framing anywhere.

## Confound controls
- K=10 min aloud-lines per resident (below → dropped; centroid unestimable).
- **2 conditions:** a verdict needs ≥2 arms PER condition (4 arms: A,A,C,C); a 2-arm n=1 (A,C) is a
  pilot with NO verdict.
- Internal contrast only; same embedder across arms; log each shard's flags + per-resident example index
  (edges-not-nodes), so attribution is deterministic.

## CRITICAL PATH (ordering is part of the lock)
1. **Stand up the embedder cadre.** [DONE]
2. **Run the SynthSTEL calibration gate.** [DONE — CIRCULAR, nothing admissible: nomic 0.00 (excluded);
   StyleDistance 0.94 but IN-DISTRIBUTION = self-consistency, NOT a pass, keep out of the admit column;
   Wegmann 0.22 below-chance = failed its OOD leg. The only passer is the model trained on the family.]
3. **Construct-agreement check — the prior question (Mr. Review round 6).** Correlate StyleDistance vs
   Wegmann per-triplet style-margins (`register_construct_check.py`); no new corpus needed. Decides
   whether the cadre shares a register axis at all — i.e. whether the robustness frame is even coherent.
   - Shared axis → step 4. [DONE — CONFIRMED: SynthSTEL r=0.14 (home-turf confound) but neutral
     ParaDetox r=0.90 → shared axis; metric family coherent. Caveat: both ~0.35 on ParaDetox =
     correlated blindness → agreement is convergent, NOT criterion, validity.]
   - No shared axis (~0 / negative) → STOP: rewrite the robustness lock; reconsider the metric family.
4. **PEER-REGISTER SELF-CHECK — the matched-to-target gate (Mr. Review round 8 + the parallax pivot).**
   Before any coarse OOD gate or published-eval citation: test whether the instrument resolves the
   contrast the experiment ACTUALLY turns on — peer-level register — against the only peer-register
   known-positive in hand: the historical hand-authored `Voice:` souls (`ww_agent/residents/`).
   `ww_agent/scripts/peer_register_check.py` (per-soul centroid distance matrix + leave-one-out
   separation z + resample stability, method from sibling project `parallax`):
   - Clean + stable separation → the instrument has the resolution the experiment needs; the published
     OOD-validity citation THEN becomes sufficient as the criterion leg; proceed to pilot.
   - Exploratory fog / acc≈chance → embedding-separability is the WRONG family for peer-register (no
     coarse gate would have shown this) → STOP; reconsider the family (lexical/syntactic fingerprints,
     n-gram divergence, LLM-judge same-speaker — not routed through a topic-leaning sentence embedder).
   **[RESULT 2026-06-08 — REFUTED.** 10 authored-distinct souls, 62 voice lines: StyleDistance
   nearest-centroid acc **0.11 vs chance 0.10** (z +0.4), stability mixed; Wegmann **0.06, BELOW chance**
   (z −0.7), stability mixed. Neither resolves souls built to differ in voice. Decisive via the CONTRAST:
   the same StyleDistance scored **0.94 on coarse SynthSTEL** — strong coarse sensitivity, ZERO
   peer-register resolution = a resolution-floor finding, not low power. **Embedding-separability via
   off-the-shelf style embedders is the wrong metric family for peer-register.** The family
   reconsideration is now the open question. Small-n caveat (~6 lines/soul) noted; does not rescue —
   coarse signal strong, fine signal absent under the same instrument + n.]
   **RESCUE-SPIRAL NOTE:** the coarse-gate build (Shakespeare etc.) AND the published-eval shortcut were
   BOTH spiral moves — efficient ways to keep the metric family alive without testing it against the real
   granularity. Held in reserve; not spent until this self-check decides.
5. Only if the self-check passes: **the 2-arm (A,C) n=1 pilot** — outputs ONLY matched-context cell
   occupancy, embedder-floor on real speech, per-arm variance; NO verdict — then the **verdict-grade
   ≥2/condition run.** The pilot may not be scheduled before the self-check passes. Ordering is locked.
   **[The self-check FAILED (step 4 result) → steps 4–5 (pilot, verdict run) are NOT taken. See Final
   Disposition.]**

## FINAL DISPOSITION (2026-06-08 — Mr. Review round 9, signed off)
The peer-register self-check REFUTED embedding-separability as the metric family. Refutation ACCEPTED;
**no higher-powered confirmation** — the within-instrument coarse-strong/fine-absent contrast is
decisive, and a confirmation run would itself be a spiral move. (Numbers accepted on logged output; the
*method* in `peer_register_check.py` is cold-verified correct by the reviewer.) Fork resolved: **(b),
bounded.**
- **SHIP arm C (`WW_VARIED_EXAMPLE`) DEFAULT-ON** — reversible, mechanism-justified de-homogenizer
  (removes the single shared few-shot shown to all 45 residents). Claim the **mechanism, not the effect**:
  "removed a population-level homogenizer; register effect UNQUANTIFIED — peer-register is below
  off-the-shelf resolution at this granularity." Revert via `WW_VARIED_EXAMPLE=0`.
- **HOLD H3** (forced-JSON / format change) — invasive + contested (.txt rebuttal); shipping it unmeasured
  is exactly what (b) forbids.
- **Do NOT build metric family four.** The refutation is broad (target below available resolution), not
  embeddings-specific; a new family is a bet against the finding with no new evidence.
- **Parallax fog thresholds (0.75/0.45) are INHERITED, not tested** this round (accuracy-at-chance drove
  the verdict; stability was only "mixed"). Do not let them travel into a future verdict unchecked.
- **RE-OPEN-MEASUREMENT TRIGGER (pre-registered):** a measurement family earns a rebuild only if a
  *coarser* register effect becomes the question, OR a specific intervention must be *credited* with an
  effect size (publication/funding). Absent such a trigger, "stop" stands — and is not "we gave up on
  rigor."
- **DON'T-LOSE-THE-EVIDENCE:** the authored `Voice:` souls (the only peer-register known-positive) are
  snapshotted to `ww_agent/scripts/fixtures/peer_register_known_positive.jsonl` (tracked), and
  `peer_register_check.py --fixture` reads it — so untracking `residents/` cannot lose the baseline.

## OBSERVATIONAL RUN RESULT (2026-06-08, the (b) "watch coherence" run)
A 15-soul A/B from the clean `ww_pdx_deal` cast — `arcon` (arm C ON) vs `arcoff` (arm C OFF), same
byte-identical cast, doula frozen, isolated, ~2h, ~270 acts/arm. Read qualitatively + with a cheap
LEXICAL count (no embedder). Findings:
- **Arm C's ONE real effect is act-kind diversification** — removing the shared *speak-to-a-person*
  example shifts residents toward making/moving (e.g. anton_volkov 15 writes / 2 speaks ON vs 1 write /
  14 speaks OFF; OFF arm more person-addressed overall, 74 vs 56). Mechanism-justified ship CONFIRMED.
- **Arm C does NOT reduce register templating — it SWAPS the template.** OFF locked on "I'm here. I
  read…" (33% of speaks); ON locked on "I've been listening…" (~27%); identical opener-diversity (0.48
  both). The population re-converges on a template regardless of the few-shot.
- **Topic monoculture severe in BOTH** (~80%: "the weight/load/frame/the fourteenth/the covenant"), and
  arm C did not touch it (ON marginally higher).
- **Conclusion:** the de-homogenization HOPE is unsupported — register/topic convergence is robust to the
  few-shot. The real driver is the shared-attention / echo dynamic (15 souls co-converging on one
  emergent narrative + one template) = the TOPIC/CASTING axis, a different and bigger lever. Ship of arm C
  stands on act-kind/mechanism alone, effect-on-register explicitly NULL.
- **Method note:** a 4-soul eyeball read "ON looks more varied"; the full lexical count refuted it (ON
  just has a different template). The cheap non-embedding count caught a confirmation-biased read in real
  time — the kind of instrument Mr. Review pointed at when the embedding family was refuted.

### BANK AND STOP (Mr. Review round 9, signed off)
Forward call: **bank these learnings and STOP. Do NOT open a topic-metric build.** The topic monoculture
is confounded with a small-cohort echo artifact (n=15 in a sealed room for 2h → one narrative attractor
is the expected behaviour of a small coupled system, not necessarily a casting defect). Building a topic
metric now would measure the artifact and the phenomenon together = the spiral in a fresh coat.
**RE-OPEN TRIGGER (pre-registered):** open a topic/casting investigation ONLY when (a) topic convergence
*persists at larger n or under federation* (ruled out the echo artifact via a CONDITION check, not a
metric) AND (b) a decision actually needs the casting axis credited. The cheap separator is varying the
condition, never a fourth ruler.
**Durable public record:** canonical numbers + cold-verifiable recompute live at
`research/runs/2026-06-08-armC-ab/FINDINGS.md` (this pre-reg is gitignored/local; the public box is the
evidence of record — the numbers there supersede any transient figures cited above).

## Known-empty reverie slice (unchanged)
ReverieDeck stays dark (it moves the drive vector, a different axis). The drive config weights `reverie`
0.35 but `DriveVector.build` is always called `reveries=()` (`cognitive_core.py:177`) → the slice is
structurally empty. Do not read 0.35 as a live signal.

## Promoted to the standing brief §3 (across rounds 3–4)
1. **An inert arm is a void, not a weak arm** — verify each arm's MECHANISM can fire against the LIVE
   data before locking (the failure that just happened: a voice-injection arm on a cast with no voice).
2. **Instrument rider:** when the known-positive is INTERNAL to the system and the system removes it,
   import an EXTERNAL known-positive and re-label the gate for the weaker claim it now supports.
3. **Cadre, not a single instrument (round 4):** with no internal ground-truth, run the metric through a
   cadre of instruments and require the result to survive instrument substitution; pre-register what a
   split across instruments means BEFORE seeing one, or a split becomes a license to pick the answer you
   wanted.
