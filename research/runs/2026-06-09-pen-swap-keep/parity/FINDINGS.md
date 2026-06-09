# Substrate-parity trace — the real faithfulness gate — FINDINGS

**Date:** 2026-06-09 · **Result: PASS, 15/15 residents.** The perception-replay harness reproduces the
substrate's perception and memory-retrieval **deterministically** on replay — not just the read pattern.

## Why this exists
The earlier keep-run reported 0/0 read-drainage (every world read served from the recording, in order,
fully consumed). Mr. Review (§1) correctly flagged that as a **proxy**: it proves the replay's read
*pattern* matches, NOT that `perceive()` parsed the same perception or that `_recall()` returned the same
set. This artifact proves the latter directly.

## Method (`ww_agent/scripts/pen_swap/parity_trace.py`)
Isolate the substrate computation from both pen stochasticity and wall-clock:
- **null-act fixed pen** — a stub returning `{felt_sense, act:null, keep:[]}` (no LLM). No acts + no keeps
  ⇒ the kept-memory store stays constant, so `recalled` is a pure function of the served perception.
- **force-ignite every tick** — guarantees the perceive→recall path runs each tick, aligned tick-for-tick.
- **synthetic clock** — deterministic `now` per tick, so time-decayed integrals are reproducible.
- **seeded RNG per resident** — see the finding below.

Then replay the SAME recording **twice on byte-identical pristine copies** and assert the per-tick
**(heard, recalled)** sequences are identical. `heard` (served) and `recalled` (relevance over a constant
store) carry no timestamps and no decay, so any divergence would be harness infidelity in
perception/retrieval — exactly the §1 gap. Arousal/surprise are logged (`parity_trace.jsonl.gz`) for
visibility but NOT gated (they are legitimately time-sensitive).

## Result
`parity_result.txt`: **PASS** for all 15 residents over 30 ticks each — `heard==True` and
`recalled==True` across both runs (450-row trace in `parity_trace.jsonl.gz`).

## §4 hardening (2026-06-09, after Mr. Review's final pre-mortem)
Seed-once is sufficient for *this* PASS but **insufficient for the experiment**, and the gate as first
built could not have seen why: it runs a null pen on BOTH sides, so the module-global RNG advances
identically and never desyncs. Under two *real* pens making different numbers of `random.*` calls, the
global state desyncs and perception's content-blind `overheard` slice silently differs between arms — noise
that mimics substrate divergence. Fix (commit f1491d8): perception's overheard draw now uses a stable
per-(resident,tick) local RNG, decoupled from global state; `parity_trace.py` now runs A vs B under
**divergent global seeds (1 vs 999)** and `(heard, recalled)` still match (3/3 verified) — proving the
decoupling against the exact failure mode, not hiding it behind identical seeds. The 15/15 result below is
the seed-once run; recompute with the hardened tool (divergent seeds) reproduces PASS.

## A real finding the gate caught on first contact
The **first** run FAILED (diverged at tick 2). Cause: perception includes a **content-blind random
`overheard` slice** (`perception._sense_overheard`), and the global RNG advanced from run A into run B
(shared process state). Not harness infidelity — genuine unseeded randomness in the perception path.
**Consequence for the experiment:** replay arms (KEEP′ / SWAP) must **seed the RNG identically**, or the
overheard slice injects noise into the KEEP′-vs-SWAP contrast. Folded into the v4 pre-registration. A gate
that catches its own confound on first contact is the gate working.

## Recompute
```
python3 scripts/pen_swap/rehydrate.py --out /tmp/pristine \
    --source research/runs/2026-06-08-armC-ab/cast \
    --ledger-from research/runs/2026-06-08-armC-ab/ledgers/arcon
WW_EMBEDDING_URL=<ollama>/v1 WW_EMBEDDING_MODEL=nomic-embed-text \
python3 scripts/pen_swap/parity_trace.py \
    --keep-dir <keep recordings> --pristine-dir /tmp/pristine --rounds 30
```
(The keep recordings are in `../recordings/`. Expect PASS 15/15.)
