# Pen vs Substrate — PRE-REGISTRATION v4 (LOCKED design, for final pre-mortem)

*v4 is the design after your causal-graph shaping. It is written to be able to LOSE: a pre-committed
FALSE region, controls as gates (not votes), and ≥2 SWAP pens to separate substrate from idiom. Cohort
grown clean (dual-pen, known provenance) so none of the armC confounds carry forward. The companion
artifact is the substrate-parity trace (the real §1 gate). Lock or break this before we grow/burn.*

## 0. The narrowed, falsifiable question (your reframe)
Walk the causal graph: the pen does **not** compute `recalled` or the drive vector (the *embedder* does) —
those are pen-invariant **by wiring**, so they persist across a swap trivially (the POSTMORTEM.md:23
pitfall). The **only** durable-state channels the pen actually authors are **(1) what gets kept** and
**(2) whom it addresses**. So the question is exactly:

> Of the two channels the pen controls — *what gets kept* and *whom you address* — does the pen's identity
> determine them more than the frozen substrate does?

## 1. Clean foundation (cohort — grown, not inherited)
- **Grown by us under known, recorded pens** → provenance by construction; the armC provenance hole (§3
  sign-inversion) cannot recur.
- **DUAL-PEN maturation (locked):** mature the cohort under **two pens alternating**, so neither pen's
  idiom is privileged in the durable state. This kills the maturation-idiom confound *by construction*
  (the §3 "home-idiom advantage" you flagged) rather than leaning on replication to back it out.
- **Structural diversity, not just bio:** multiple locations / smaller close-contact clusters (not one
  sealed `city` room), so **directed reciprocal dyads** actually form. Heterogeneous soul-domains too, but
  the relationship density is the point — bio-diversity alone still echoes into monoculture (armC's own
  finding).
- **Stop on a stability line, not a tick count:** mature until **≥K reciprocated dyadic edges/resident**
  (per the brief's stop-rule) and the edge graph clears the concentration bar (**≥3 dyads, top-dyad <
  50%**). If it never reaches that, the cohort can't support the relational axis — say so and don't run it.

## 2. Arms (all REPLAYS — clean floor)
Record the cohort's lived experience once; **every divergence operand is a replay** (your §4 — KEEP is the
perception *source*, never a live-vs-replay operand, so the floor is replay-vs-replay and all arms share
the replay condition):
| arm | pen | role |
|---|---|---|
| **KEEP-replay** | maturation pen A | reference self |
| **KEEP′** | pen A again | same-pen **noise floor** |
| **SWAP-B, SWAP-C (≥2)** | two foreign pens | the test — **≥2 is load-bearing**: same-direction divergence = substrate-carried; different-direction = mere idiom |

**RNG seeded identically per resident across all arms** (parity_trace surfaced this): perception has a
content-blind random `overheard` slice; unseeded, it adds noise to KEEP′-vs-SWAP. Seed so the only
inter-arm difference is the pen.

## 3. Measurement — 2 self-axes + 4 controls, all DETERMINISTIC (no embedding-content alignment)
**Self-axes (carry the verdict):**
- **A1 — addressing fidelity (relational).** Content-conditional: of person-addressed acts, *which
  established peers* (name-match against the resident's pre-fork dyads), SWAP vs KEEP′. Read *which*, not
  *how many* (rate is pen-disposition). Score above a degree-preserving shuffle null; concentration bar.
- **A2 — keep-choice/content (declarative), SECONDARY/content-conditional.** *When* a keep co-fires in
  both arms, is the kept content the same realization (entity/decision match, deterministic). **Dedup:
  count re-keeps** (re-keeping a realization is itself curation; do not collapse identical notes);
  near-paraphrase flagged as noise. Pre-declared **likely pooled-only / possibly INCONCLUSIVE on volume** —
  keeps are sparse and may differ mainly in phrasing (surface).

**Controls — GATES, not votes (they read pen-invariant inputs; they CANNOT fail unless the harness is broken):**
- **C1 memory-reference** (which `recalled`-not-`heard` entities the act names) → must HOLD; if it
  collapses, parity/harness is broken → INCONCLUSIVE.
- **C2 drive/concern fidelity** (act aligns with soul-domain anchors) → must HOLD; doubles as the
  "selves are actually distinct" check on the cohort.
- **C3 act-kind mix** → pen-SURFACE (armC arm-C moved it with a few-shot) → expected to shift; not self.
- **C4 register/theme** → MUST shift = proves the swap took (the **discriminant** check, MTMM).

## 4. Verdict + irreducibility (FALSE region pre-committed; controls gate, don't vote)
- **HOLDS:** A1 (and A2 where powered) track the KEEP′ floor across **≥2 SWAP pens**, **AND** C4 shifts,
  **AND** C1/C2 hold (harness sound).
- **FALSE:** a self-axis **collapses below the KEEP′ floor across ≥2 pens, same-direction**. *(This region
  exists by construction — if the design can't produce it, we stop and redesign.)*
- **PARTIAL (pre-named, both directions):** exactly one self-axis collapses — "substrate carries declarative
  curation but not relational disposition," or vice versa.
- **IRREDUCIBLE (the pre-registered split):** SWAP pens diverge in **different directions** → it's pen-idiom,
  not substrate (≥2-SWAP disambiguation). Reported as irreducible, not as HOLDS.
- **INCONCLUSIVE:** C4 didn't shift (bad swap) **OR** C1/C2 collapsed (broken harness) **OR** KEEP can't beat
  its own null (no signal to lose).
- **Load-bearing rule:** only A1/A2 carry the verdict. C1–C4 are gates. Counting controls toward
  "convergence" would rig it toward HOLDS (they can't fail) — the correlated-blindness trap.

## 5. The parity gate (companion artifact — the REAL §1 gate, not the 0/0 proxy)
`parity_trace.py`: replay with a **null-act fixed pen + force-ignite + synthetic clock + seeded RNG**, twice
on byte-identical pristine copies, and assert the per-tick **(heard, recalled)** sequences are identical —
proving `perceive()` parsed the same perception and `_recall()` returned the same set, deterministically.
(Arousal/surprise logged but not gated — they're time-decayed.) Result delivered with this prereg; no
divergence number counts until it PASSES.

## 6. Confounds, and how each is handled
- **maturation-idiom fingerprint** → dual-pen maturation (by construction) **+** ≥2-SWAP same-vs-different
  direction (backstop).
- **correlated blindness** (convergent ≠ criterion validity) → the cull: only the 2 pen-authored channels
  vote; pen-invariant axes are gates.
- **recalled-triviality** → demoted to control C1.
- **keep base-rate = pen disposition** → A2 read content-conditional (co-fire content), never count.
- **perception RNG** → seeded across arms.

## 7. Grounding (lean on the known; spend on the departure)
The swappable-pen is a *named* design pattern; *Agent Identity Evals* (arXiv 2507.17257) formalizes
identity metrics but **never tests a base-model swap** and leans on embedding distance — so our deterministic,
under-swap test is the departure. Synthesis = **MTMM / multiple operationism** (Campbell & Fiske 1959):
convergent validity across the self-axes, **discriminant** validity from C4, and a named home (irreducible)
for non-convergence.

## 8. Scope (stated, not hidden)
Necessary, not sufficient: this tests pen-robustness *given an identical replayed life*. A pen could curate
identically under replay yet, in free-run, steer into a different life over time — the replay can't see that;
a "HOLDS" does not upgrade to the lifetime "swappable pen" claim.

## 9. For your pre-mortem
Predict the §4 branch. Is the FALSE region genuinely reachable, or is A1 still pen-invariant enough (target
set from recall) to make HOLDS over-determined? Does dual-pen maturation introduce a blend-confound (a self
authored by *two* idioms — foreign to *both* SWAP pens equally)? Name the confound that survives the cull.
