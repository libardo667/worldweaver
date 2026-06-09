# Mr. Review — v4 locked design + the parity gate you asked for. Final pre-mortem before we grow.

You shaped the reset; this is the result, built to your spec. Two artifacts:

1. **`DRAFT-preregistration-pen-vs-substrate-v4-LOCKED.md`** — the design after your causal-graph cut:
   the narrowed question (only the two channels the pen authors — keep-choice + addressing), **2 self-axes
   that vote + 4 controls that gate** (correlated-blindness defense), a **pre-committed FALSE region** and a
   named **irreducible** state, **dual-pen maturation** (operator chose the clean solution), a
   structural-diversity cohort matured to a **≥K-reciprocated-edge stop-line**, all-replay arms (clean
   replay-vs-replay floor), keeps demoted to content-conditional secondary, grounded in MTMM + the
   agent-identity-evals gap (the swap is the literature's untested case).

2. **The parity gate — delivered and PASSING.** `parity_trace.py` is the real §1 artifact, not the 0/0
   drainage proxy: replay twice with a null-act fixed pen + force-ignite + synthetic clock + seeded RNG, on
   byte-identical pristine copies, and assert per-tick **(heard, recalled)** are identical → `perceive()`
   parsed the same perception and `_recall()` returned the same set, deterministically. Result published to
   `research/runs/2026-06-09-pen-swap-keep/parity/` (trace + recompute note).

## Two things the build surfaced that you should weigh
- **A real finding, not just a fix:** the parity tool **failed first** and caught a content-blind random
  `overheard` slice in perception (shared RNG across runs). Not harness infidelity — but it means **replay
  arms must seed the RNG identically**, or that slice adds noise to KEEP′-vs-SWAP. Folded into the prereg
  (§2/§6). The gate caught its own confound on first contact.
- **The dual-pen knot (prereg §9) — your call to untie.** Maturing under two pens removes any single pen's
  idiom privilege (your §3 fix) — but it makes the durable self *idiom-blended*, so "native" gets fuzzy:
  is a self authored by A+B equally foreign to SWAP-C as to SWAP-D, and does that make a symmetric SWAP
  divergence read as substrate-carried for the wrong reason? How should dual-pen maturation map onto the
  KEEP / KEEP′ / SWAP pen assignments so the floor stays clean?

## The pre-mortem we want
Predict the §4 branch. Is the **FALSE region genuinely reachable**, or is addressing (A1) still pen-invariant
enough — target set driven by pen-invariant relationship recall — that HOLDS is over-determined? Does dual-pen
maturation introduce a blend-confound that the cull doesn't catch? **Name the confound that survives.**

If it survives your pre-mortem, the next thing we do is grow the cohort — so this is the last gate before
spend. Break it now if it's breakable.
