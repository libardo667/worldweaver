# Mr. Review — round 8 (2026-06-08): the null, the locked falsifier, the edge-schema

*External review of the venture-OFF pre-test package. He took the "turn the raw against us" invitation
and built the degree-preserving target-shuffle null the instrument was missing.*

## What he did

Built a **degree-preserving target-shuffle null** — permute who-addresses-whom, hold every speaker's
volume and every person's in-degree fixed, recompute the windowed answer rate, 400 draws. Asks: is the
turn-taking above what pure co-present chatter would produce at the same volume? The null reversed HIM
on two of three cohorts.

| cohort | moves | outwardness | turn-taking@5min REAL | NULL (chance) | verdict |
|---|---|---|---|---|---|
| on_argmax | 12 | 40% | 0.5% (1) | 1.2% (2.4) · z −0.97 | **at/below chance** |
| gemini_handonly | 13 | 53% | 28.2% (51) | 2.2% (4.0) · z +23.6 | **far above chance** |
| claude_handonly | 42 | 92% | 5.6% (11) | 1.6% (3.2) · z +4.9 | above chance, but one couple |

Findings: the instrument detects REAL directed turn-taking (gemini_handonly = genuine conversation,
6 dyads, ~12× beyond chance — his co-presence-density reversal is FALSE there). But it lands hard on
**`on_argmax`** — the venture-ON/argmax cohort the original "33% contact / a real we" came from has
turn-taking **at or below chance**. That "contact" was outwardness; under a chance baseline there is no
reciprocation in it. Reciprocity is **decoupled from, even anti-correlated with, movement and
outwardness** — claude_handonly moved most + addressed most + bought least; gemini moved least +
reciprocated most. **Real engagement tracks doula-mode / seed-model, not motion.**

## Ask 1 — the falsifier, LOCKED

On the OFF-vs-ON single-axis bench, read with reciprocity.py + the shuffle null:
- **Metric:** directed turn-taking at the **5-min window** (15-min robustness), scored as **REAL −
  target-shuffle NULL** (or z), never raw rate.
- **Concentration control:** excess carried by **≥3 distinct dyads** with **top-dyad share < 50%**
  (one couple ≠ population engagement); report per-capita answered volume alongside.
- **"Venture buys engagement"** accepted ONLY if: ON null-relative turn-taking clearly above chance
  (z>2, real>null p95), multi-dyad, AND exceeds OFF's null-relative turn-taking beyond noise — i.e.
  removing venture **collapses real answering toward chance**.
- **"Venture buys only outwardness/motion"** if: ON has more moves/outwardness/volume than OFF BUT the
  **null-relative** turn-taking is NOT higher in ON than OFF (OFF keeps above-chance answering despite
  moving less).
- **Guardrails:** (i) outwardness dropping in OFF is expected under both, counts for nothing; (ii) raw
  count dropping is insufficient — must drop relative to its own null; (iii) single-dyad disqualified;
  (iv) headline window is 5-min, no retreat to unbounded.
- **His committed prediction:** venture-OFF will RETAIN above-chance multi-dyad reciprocity comparable
  to its ON twin (same hand-only seed) → bench shows **outwardness/motion, not engagement**. If OFF
  instead tanks to chance while ON holds, that falsifies him and venture earns "engagement."

## Ask 2 — spend-gate

Frozen+null **already settles the strong claim**: movement & outwardness do NOT buy engagement
(decisively; the cohort doing most of both bought least). So for "does motion produce engagement," the
OFF arm is confirmatory/skippable. BUT worth running for the **sharper** thing the null exposed: the
banked claim "venture is the contact lever" rests on `on_argmax`, whose reciprocity is **chance-level**
— a load-bearing belief now in doubt, and the OFF arm is the only **clean single-axis** test of whether
venture touches real reciprocity at all (model/doula/run-length confounds removed). **Run it, re-aimed:**
headline = null-relative reciprocity, not outwardness; live hypothesis = **"engagement is doula/seed-
gated, venture-irrelevant."** Caveat: gemini_handonly's reciprocity survives the VOLUME null but maybe
not a **model-style** prior (gemini may just write named turn-taking-shaped dialogue) — same-seed
ON-vs-OFF controls it; if it's style, reciprocity is identical across arms → again venture-irrelevant.

## Ask 3 — the schema: LOG EDGES, NOT JUST NODES

The reason metrics keep re-litigating: the ledger records **node-events** (resident did X) while every
contested claim — contact, reciprocity, convergence — is about **edges** (A perceived B; A replied to B;
A co-located with B). Edges are reconstructed heuristically (windowed coincidence) → "reciprocity"
ranged 0.5–32% by window×concentration. Log edges at formation → every relational metric becomes a
deterministic query, no heuristic, no narrative; the desk self-populates. Minimal additions:
- **`event_id`** on every act (stable utterance identity; today keyed by resident+ts, fragile).
- **co-presence**: `location` + `co_present:[ids]` on `pulse_act_emitted` (+ periodic
  `session_state_observed`) → reciprocity **opportunity-conditioned** (an unanswered A→B where B wasn't
  present is no-opportunity, not a snub). The concentration control, logged not inferred.
- **`perceived` / `perceived_by:[ids]`** on the utterance: which residents actually ingested it →
  "B perceived A and answered," not "B spoke within W."
- **`in_reply_to: <event_id>`** when a pulse was triggered by a perceived utterance — the substrate
  knows what surprised it into speaking. Reciprocity becomes a counted reply-edge; reciprocity.py can
  drop WINDOWS entirely.
- **`resident_seeded`**: dealt-hand fields + `seed_model` + `doula_mode` at spawn (the disposition-
  never-logged blocker; what made the gemini-vs-claude casting disambiguation possible — bake it in).
- **`cohort_config`**: single-axis declaration (venture, targeting, model, doula_mode, geo, window,
  isolation) — the confound table, logged instead of hand-written.

**Canonical turn-taking definition (blessed):** *an A→B person-addressed utterance is reciprocated iff
B emits an act with `in_reply_to` pointing at it (until that field exists: a B→A person-addressed
utterance within **5 minutes**, where co-presence logs show B was present). Population reciprocity =
reciprocated ÷ A→B utterances with B co-present (opportunity-conditioned), reported as REAL −
degree-preserving target-shuffle null, with distinct-dyad count and top-dyad share. Headline = null-
relative rate at 5 min. Unbounded is never the headline.* One-line version: **you've been logging what
each mind DID; start logging what passed BETWEEN them, and the arguments about the numbers mostly stop.**
