# Venture-OFF bench — PRE-REGISTRATION (committed before the run)

*Locked 2026-06-08 after Mr. Review's pre-launch pre-mortem. Committed before any data exists, so the
acceptance rule cannot be moved after seeing the numbers. Mr. Review predicts a NULL ("venture buys
outwardness/motion, not engagement; engagement is doula/seed-gated"); this protocol is built to be able
to falsify him.*

## The metrics (Ask 2 — roles locked)
- **PRIMARY (pre-registered):** directed turn-taking @5-min window, scored as **REAL − degree-preserving
  target-shuffle null** (z), via `reciprocity.py`. Chosen as primary because the frozen cohorts also have
  it → preserves comparability.
- **SECONDARY (convergent, stricter):** the deterministic **`in_reply_to` reply-edge** (Major 66 Phase 1)
  — a counted logged reply, no window, no chance-null needed (an edge has no coincidence to subtract).
- **TIE-BREAK (locked):** if edge and windowed-null disagree, **the edge wins, in the conservative
  direction** — a logged reply beats a temporal coincidence, so the edge can only *tighten* the verdict,
  never loosen it.
- **CONCENTRATION BAR (applies to BOTH metrics, unchanged):** the excess must be carried by **≥3 distinct
  dyads** with **top-dyad share < 50%**. One ping-ponging couple is not population engagement.

## The verdict rule
- **"Venture buys engagement"** accepted ONLY if: ON's null-relative turn-taking is clearly above chance
  (z>2, multi-dyad per the bar) AND **exceeds OFF beyond the measured noise band**, i.e. removing venture
  **collapses real answering toward chance** while ON holds.
- **"Venture buys only outwardness/motion"** (Mr. Review's prediction): ON has more moves/outwardness than
  OFF BUT the **null-relative** turn-taking is **not** higher in ON than OFF.
- **Guardrails:** outwardness/raw-count drops in OFF count for nothing; single-dyad disqualified; 5-min is
  the headline window, no retreat to unbounded.

## Conditioning — PERCEIVED, not co-present (Mr. Review round-2, the decisive correction)
The opportunity to condition on is **"did the addressee PERCEIVE the overture,"** NOT "was B physically
co-present." They come apart *because* the OFF arm's contact runs through broadcast + letters
(non-co-located by definition). Conditioning on `co_present` would compute OFF's rate over the tiny
co-located subset and **discard the exact channel the OFF arm uses** — erasing the baseline, not
coarsening it. The whole question is "does movement add engagement *beyond the phone*"; a co-presence
denominator throws the phone away. So:
- **Numerator** = reply-edges (B perceived A's overture AND answered it).
- **Denominator** = person-addressed overtures **B actually perceived** — channel-agnostic (speech OR
  broadcast OR letter). Verified: perception is **utterance-discrete** (the `heard` set is discrete
  utterances each with a backend msg id), so this is logged directly, not proxied — the resolver already
  consults that set. (Fallback only if perception were ambient-by-location: condition on *delivery via
  any channel* — co-present OR broadcast-reach OR letter-received — never co-present alone.)
- **DO NOT build Phase-2 `co_present` for this run** — it's the right tool for spatial questions later,
  the wrong conditioner for this falsifier.

## Confound controls (Ask 1)
1. **MIN-OVERTURE INCONCLUSIVE GATE (kept — distinct job from perceived-conditioning).** Perceived-
   conditioning fixes the *systematic* bias (don't penalize A for B never hearing); the gate fixes the
   *power* problem (too few perceived overtures in OFF to estimate a rate at all). **Pre-gate a minimum
   OFF perceived-overture volume below which the run is INCONCLUSIVE, not a venture win.** Need both.
2. **REPLICATION — 2+2 is the FLOOR, not the proof.** Two per condition buys a within-condition check
   (are the two ON arms closer to each other than to the OFF arms?), not a good noise-band estimate.
   **Pre-registered: if the ON−OFF difference lands INSIDE the within-condition spread, the result is
   INCONCLUSIVE → escalate to 3+ arms, do not call it.**
3. **INTERNAL CONTRAST ONLY.** The re-deal means this cast is NOT comparable to gemini_handonly's
   absolute numbers — **read ON-vs-OFF within THIS run only; do not anchor on "z was +26 last time."**
4. **SEED MODEL HELD CONSTANT = GEMINI across all four arms.** Gemini is the one cohort with measurable,
   un-floored reciprocity (28–32%, with headroom). Seeding a near-floor model (deepseek/claude) would
   under-power the venture contrast before the run starts. (NB: change `WW_DOULA_MODEL` from the shards'
   current deepseek-v3.2 to gemini for the re-deal.)
5. **PRE-ACQUAINTANCE — the re-deal IS the fix.** 29/30 of the *old* cast named another resident
   (resumed relationships inflate baseline, can ceiling-mask venture). A FRESH 50-soul deal means
   reciprocity must *form* in-run, not resume. Re-grep the new cast to confirm the level dropped.
6. **DENSITY (asymmetry pre-committed).** ~30 souls biased TOWARD a null (less co-location = venture's
   mechanism). **At 50: a POSITIVE result is strong; a NULL is weaker and density-scoped.**

## The reply-edge must be READ-FROM, not ELICITED (Ask 3 — verified)
`in_reply_to` is resolved **substrate-side** by matching the act's target to an utterance already in the
pulse's perceived input (the heard list) — the model is **never prompted** "which utterance are you
answering?". The write is off the critical path (no added latency reordering perception). This keeps it
**observational** (pure logging, safe to add mid-investigation), NOT a reflective targeting step that
would inflate reciprocity itself. If it were ever elicited, it would be a cognitive change wearing a
logging hat and must be held out of the experimental arm.

## Design delta from the teed-up bench
The teed-up arms (`ww_pdx_von`/`ww_pdx_voff`, 30 souls, n=1 each) are **insufficient** per the above.
Revised target: **2+2 arms, 50-soul fresh hand-only cast cloned identical across all four, doula frozen,
single axis `WW_ACTION_TENDENCY`, isolated**; reciprocity read opportunity-conditioned with the
min-overture inconclusive gate; `in_reply_to` (read-from) logged for the secondary metric.
