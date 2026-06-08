# Arm C (varied few-shot) A/B — FINDINGS

**Date:** 2026-06-08 · **Status:** BANKED (Mr. Review round 9 sign-off: "bank and stop") · **Result: register effect = NULL; arm C is act-kind diversification only.**

## What was tested
Arm C = the `WW_VARIED_EXAMPLE` lever: replace the single shared few-shot example in the pulse contract
(one `speak`-to-a-person, shown identically to all residents) with a per-resident name-hashed entry from a
neutral pool. Shipped default-on, on **mechanism alone** (effect unquantified) — the prior arc established
that peer-register sits below off-the-shelf embedding resolution, so this run is an **observation**, not a
measurement.

## Setup
- 15-soul A/B from the clean `ww_pdx_deal` cast (the live doula-seeded Portland cast; **no authored `Voice:`**).
- Same byte-identical 15 souls in both arms; **doula frozen** (`WW_DOULA=0`); isolated (no federation root); ~2h.
- `arcon` = `WW_VARIED_EXAMPLE=1` (arm C ON) · `arcoff` = `WW_VARIED_EXAMPLE=0` (OFF / shared example).
- Full setup/teardown recipe: cognition memory `shard-controlled-ab-arm-recipe`. Cast: see `cast/`.

## Results (recompute: `python3 analysis/lexical_count.py` over the gzipped ledgers in `ledgers/`)
*Numbers are what the committed ledgers produce — recompute and they will match (they drifted slightly
from the live read taken mid-run; these are the durable, verifiable values.)*
| metric | arcon (ON / varied) | arcoff (OFF / shared) |
|---|---|---|
| acts | 272 | 261 |
| speaks | 213 | 216 |
| topic-monoculture (weight/load/frame/the-fourteenth/…) | **86.4%** | **80.6%** |
| templated opener ("I'm here / I read …") | **0.0%** | **33.8%** |
| distinct 3-word openers / speaks | **0.49** | **0.48** |
| top opener | "I've been listening" (~25%) | "I'm here. I…" (I'm-here/I-read family 33.8%) |
| act-kinds | speak 213 / **write 56** / move 3 | speak 216 / write 18 / **move 27** |
| person-addressed speaks | 82 | 89 (marginal) |

## Conclusion
1. **Arm C's one real effect is ACT-KIND diversification.** Both arms speak about equally (~215); the
   difference is the *non-speak* mix — ON skews to **writing** (56 vs 18), OFF to **moving** (27 vs 3)
   (anton_volkov: 15 writes/2 speaks ON vs 1/14 OFF). Removing the shared *speak-to-a-person* anchor
   genuinely shifts what residents *do*. The mechanism it shipped on is real. **Ship stands, on act-kind.**
2. **Arm C does NOT reduce register templating — it RELOCATES it.** OFF locked on "I'm here. I read…"
   (33%); ON locked on "I've been listening…" (~27%); identical opener-diversity (0.48). The population
   re-converges on a template regardless of the few-shot.
3. **Topic monoculture is severe in BOTH** (~80%) and untouched by arm C.
4. **Effect-on-register = NULL.** The de-homogenization hope is unsupported; register/topic convergence is
   robust to the few-shot. Shipping on mechanism (not effect) was the correct, now-vindicated scope.

## Method note
A 4-soul eyeball read "ON looks more varied." The full lexical count across ~215 speaks/arm **refuted** it
(ON just has a *different* template). A cheap non-embedding count caught a confirmation-biased read in real
time — the instrument family that replaced the refuted embedding approach earned its keep.

## The next axis — CONFOUNDED, do not build a metric for it
The real driver of convergence is the **shared-attention / echo dynamic** (15 souls co-converging on one
emergent narrative + one template) = the **topic/casting axis**. But at **n=15 in a sealed room for 2h**,
one narrative attractor forming is the *expected* behavior of a small coupled system — so the monoculture
is **confounded with a small-cohort echo artifact** and is not yet a coherent measurement target.

**RE-OPEN TRIGGER (pre-registered):** open a topic/casting investigation ONLY when **(a)** topic
convergence *persists at larger n or under federation* (ruling out the echo artifact, via a **condition
check**, not a metric build) **AND (b)** a decision actually needs the casting axis credited. Until both,
this stays a logged observation. The cheap separator is varying the *condition* (scale/federation), never
a fourth ruler.

## Provenance
Numbers were operator-observed at run time; they are now **cold-verifiable** from the gzipped ledgers in
`ledgers/` via `analysis/lexical_count.py`. The live `shards/ww_pdx_arc*` runtime stays gitignored
(secrets); this is the durable, public copy of the evidence.
