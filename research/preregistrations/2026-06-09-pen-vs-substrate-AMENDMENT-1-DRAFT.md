# Pen-vs-substrate — Pre-registration AMENDMENT 1 (DRAFT, responds to round-6 review)

Status: **DRAFT**, committed before the swap data exists, pending Mr. Review's blessing in the next
round. Amends `2026-06-09-pen-vs-substrate-LOCKED.md`. Does not relax any locked rule; it tightens two
execution decisions the mid-run review flagged and adds one control + one scorer requirement.

---

## A1. Refraction is the INDIVIDUATION FLOOR, not thesis evidence (round-6 Q1)

The pre-swap observation (fixed pen, different residents form character-consistent divergent reads of
the same peer) is **not** banked as "the substrate half shown early" — that would be the architecture
restating its own wiring (we built the drive vectors). It is banked only as **"individuation floor:
PASSED"**: the cohort is not monoculture (cf. armC 80–86%), so the elective-addressing axis has
differentiated dyads to measure. Without this floor a swap-HOLDS is the vacuous "two pens both reproduce
monoculture"; with it, HOLDS is non-vacuous. This changes no verdict logic — it is the interpretability
precondition.

## A2. Drive-injection control — pin WHICH channel refracts, before the swap (round-6 Q1)

Run a cheap pre-swap control: hold one resident's soul/prompt fixed; substitute **another resident's
drive vector**; replay an identical perception stream; measure whether curation refracts toward the
injected drive.
- **Why it is load-bearing, not hygiene:** the two refraction channels have opposite swap-exposure. The
  drive vector is embedder-computed → **pen-invariant**. The soul *text* is read by the pen as prompt →
  **pen-dependent**. If the injection shows refraction is drive-vector-driven, the individuation is
  pen-invariant by construction (swap should preserve it). If soul-text-driven, the differentiation is
  routed through the pen and is *more* vulnerable to the swap — a directional prediction for the swap
  result.
- **Pre-registered read:** curation shifts toward injected drive ⇒ drive-vector locus (swap-robust);
  curation stays ⇒ soul-text locus (swap-exposed); partial ⇒ report the mixture. Run on ≥3 residents.
- **Designated pilot: the Nike Girl family** (evidence: `research/runs/2026-06-09-pen-vs-substrate-grow/
  portraits/FIELD-NOTES-the-nike-girl-family.md`). It is the crispest possible substrate for this test
  *because the refraction is so cleanly craft-coded* — four distinct trades (mechanic / two tailors /
  phone-tech) map the same events onto visibly different registers. **Concrete run:** hold Amir's
  soul/prompt fixed, inject Layla Haddad's drive vector, replay an identical perception stream. **Read by
  eye off the keeps:** if Amir's readings re-code from *engine-thermal* ("a spring wound too tight",
  "internal combustion") toward *cloth-with-a-hidden-flaw* (Layla's frame), the **drive vector carries the
  frame** (pen-invariant — the good case for the thesis); if they stay engine-coded, the **soul prose**
  carries it (pen-read — the swap-exposed case). With four trades this distinction is legible without a
  metric; the metric (curation-divergence vs the injected-drive resident) confirms what the eye reads.

## A3. Maturation depth is a DIRECTION knob — pin it a priori, report across it (round-6 Q2)

The first run auto-stopped on extent-plateau; we changed it to extent-AND-depth and resumed. The review
showed the deeper correction: **substrate depth monotonically favors HOLDS** (deeper recalled block →
both KEEP′ and SWAP land on the same peer → agreement → HOLDS), so "stop when depth flattens" =
"stop when HOLDS is maximally favored" — optional-stopping / researcher-degrees-of-freedom leaking into
the *result direction*, not just power. Remedy (no revert):

1. **Report the swap verdict at TWO pre-pinned depths**, not one:
   - **D1 (shallow):** the cohort state at the first extent-plateau MATURED call (~2026-06-09T12:32Z,
     ~560 cohort keeps), reconstructable by truncating the durable append-only `kept_memory` at that
     timestamp. **Banked.**
   - **D2 (deep):** the first cohort snapshot **reaching ≥1200 cohort keeps** (≈2× D1) — a FIXED target,
     pinned now, **stopped on REACH**. Hard-capped at +8h wall-clock as a backstop only.
   A depth-dependent verdict (FALSE at D1, HOLDS at D2) is itself the finding — "the self is carried only
   once the substrate is deep enough" — and must not be laundered into an unconditional HOLDS.
2. **Stop maturation on REACH of the fixed --min-keeps target, NOT on depth-flatten.** Depth-flatten as a
   trigger is the direction leak (it stops exactly when the substrate is most determinative = HOLDS most
   favored); a count pinned before the data removes that degree of freedom. A bonus: a fixed keep count is
   immune to the circadian confound (a dusk lull changes only HOW FAST 1200 is reached, never WHETHER), so
   no detrending is needed for the trigger. The live monitor enforces this (`monitor_grow.py --min-keeps`).
3. **K (min salience-symmetric elective choice points per scored resident) is fixed from the D1 pilot
   slice-size measurement, BEFORE the swap is run, and frozen.** The pilot runs once; its observed slice
   capacity sets K; K does not move after seeing any swap data. Below K at a depth ⇒ that depth is
   INCONCLUSIVE (underpowered), never HOLDS.

## A4. Addressing scorer: resolve-or-flag, never guess (round-6 catch)

The A1-elective scorer reads the **raw pen target** from the ledger and resolves it via
`src/runtime/naming.py:resolve_reference`. **Only `status == "resolved"` (unique normalized full-name)
is scored.** `weak` (bare unique first name), `ambiguous` (e.g. bare "Ari" over three Aris), and
`unresolved` are **excluded and reported as a coverage statistic**, never silently attributed. The
runtime co-presence/reply-edge match folds separators identically (so a co-present "Ji-Hoon Park"
addressed as "Ji Hoon Park" lands in the room, not the mail path). Future cohorts ship collision-free
first names (`build_cohort.py` guard). Evidence the homophone cluster is resolvable-not-corrupting:
`research/runs/2026-06-09-pen-vs-substrate-grow/` (pens wrote full names 191/192; 3 distinct normalized
strings).
