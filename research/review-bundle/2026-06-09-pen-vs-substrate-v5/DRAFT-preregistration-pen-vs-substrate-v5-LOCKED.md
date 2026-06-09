# Pen vs Substrate — PRE-REGISTRATION v5 (LOCKED) — your 3 fixes + the pen-design reversal

*v5 implements your final pre-mortem exactly. It's a focused delta on v4 (which you hold); the unchanged
structure — controls-as-gates, the all-replay floor, A2 as content-conditional secondary, the grounding —
stands. Confirm the fixes landed and the FALSE region is now reachable, or break it. After this, the next
move is growing the cohort.*

## Change 1 — pen design: single-pen + ≥2 foreign SWAP (dual-pen DROPPED, your §3)
Your analysis flipped it: turn-alternation does **not** give idiom-balance in the durable state (keep/
address *rate* is pen-disposition → the heavier-curating pen authors disproportionately more of the keeps
and edges), so dual-pen was idiom-*dominant* wearing a balanced label, and "using it right" was a 5-arm /
4-pen design. **Single-pen maturation + ≥2 foreign SWAP pens** is simpler and handles idiom through a test
we already run:
- **KEEP = maturation pen A; KEEP′ = A** (same-pen noise floor).
- **SWAP-B, SWAP-C = two foreign pens.** Disambiguation: **same-direction** divergence across B and C =
  substrate-carried (real); **different-direction** = pen-idiom (the pre-registered IRREDUCIBLE state).
- The home-idiom advantage (A is fluent in the self it authored) is now *named*, and the ≥2-foreign-
  same-direction test backs it out — no dual-pen needed.

## Change 2 — A1 partitioned: reply-reflex is a CONTROL, elective is the verdict (your §2)
A1 as written floats to HOLDS because, in a replay, *whom you can address is mostly fixed by the replayed
perception* (reply to whoever just spoke) — that **reply-reflex is pen-invariant** (KEEP's recorded `heard`,
identical across arms) and would floor A1 so FALSE is unreachable. So:
- **A1-reflex (reply to a just-perceived speaker)** → demoted to a **CONTROL** (must hold; if it doesn't,
  the harness is broken).
- **A1-elective** → the **verdict-carrier**: the only ticks with genuine pen-dependent relational freedom —
  (a) **multiple established peers co-present**, forcing a choice among them, and (b) **unprompted
  initiation toward an absent established peer**. The verdict is scored on **A1-elective alone**, content-
  conditional (which established peer, vs a degree-preserving shuffle null, concentration bar).

## Change 3 — cohort must MANUFACTURE elective choice points (your §2)
A1-elective is sparse and a convergent cohort produces almost none (armC: 5 directed carries). So the cohort
stop-line gains a second gate: mature until **≥K elective-addressing choice points / resident** (engineered
by structural co-presence — multiple established peers reliably in-room together, parallel ongoing dyads) —
alongside the **≥K reciprocated edges** and the concentration bar. If it can't reach both, A1-elective is
unpowered → INCONCLUSIVE, not a verdict, and we say so before running.

## Change 4 — perception RNG decoupled (your §4) — DONE and PROVEN
The content-blind `overheard` slice drew from the module-global RNG, which the pulse path churns by
different amounts per pen → under real pens the slice silently desyncs across arms (noise mimicking
substrate divergence), and the null-pen-both-sides gate could not see it. **Fixed:** perception's overheard
draw now takes a stable **per-(resident, tick)** local RNG (crc32, cross-process), threaded
`tick_once(perception_seed=) → perceive → _sense_overheard`; default unchanged for production (235 tests
pass). Pulse-path RNG stays global (pen stochasticity, absorbed by the KEEP′ floor). **Proven:** `parity_
trace.py` now runs A vs B under **divergent global seeds (1 vs 999)** and `(heard, recalled)` still match —
the leak is closed, not hidden. (committed f1491d8)

## Locked verdict rule (restated with the partition)
- **HOLDS:** A1-**elective** tracks the KEEP′ floor across **≥2 SWAP pens, same-direction**, AND C4
  (register) shifts, AND the controls hold (incl. A1-reflex, C1 memory-ref, C2 drive).
- **FALSE:** A1-elective **collapses below the KEEP′ floor across ≥2 pens, same-direction.** *Now reachable*
  — elective addressing is genuinely pen-authored, so it can fail.
- **IRREDUCIBLE:** SWAP pens diverge in **different directions** → pen-idiom, not substrate.
- **PARTIAL:** A2 (keep-content, pooled secondary) and A1-elective split.
- **INCONCLUSIVE:** C4 didn't shift (bad swap) / a control collapsed (broken harness) / KEEP can't beat its
  null / A1-elective unpowered (cohort lacks choice points).
- Controls **gate, don't vote** (correlated-blindness defense, unchanged).

## Unchanged from v4 (still locked)
All-replay floor (clean replay-vs-replay); A2 keep-content = content-conditional pooled secondary, dedup =
count re-keeps; parity gate (now the §4-hardened version, PASS 15/15); MTMM convergent+discriminant framing;
*Agent Identity Evals* gap (the swap is the literature's untested case); scope = necessary-not-sufficient.

## For your pre-mortem (last gate before we grow)
1. **Is the FALSE region now reachable?** A1-elective is pen-authored — but is it *enough* signal, or will it
   collapse straight to INCONCLUSIVE (too few choice points even on an engineered cohort)?
2. **Does single-pen + ≥2-foreign-same-direction cleanly separate substrate from idiom**, given A is the home
   pen? Is there a residual home-advantage the ≥2-foreign test doesn't back out?
3. **Name the confound that survives this cull.** If none does, we grow the cohort next.
