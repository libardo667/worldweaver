# Pen-vs-Substrate — KEEP recording run + parity check — FINDINGS

**Date:** 2026-06-09 · **Status:** harness PROVEN FAITHFUL (parity clean); divergence read NOT yet
run — the curation surface (`memory_kept`) came back **starved**, pending Mr. Review cross-check.

This is the live KEEP run of the perception-replay experiment (the v3 design published at
`research/review-bundle/2026-06-08-pen-vs-substrate-v2/`). Harness: `ww_agent/scripts/pen_swap/`.

## Setup (cold-reproducible)
- **Cohort:** the 15-soul armC cast, rehydrated from PUBLIC data —
  `rehydrate.py --source research/runs/2026-06-08-armC-ab/cast --ledger-from .../ledgers/arcon`.
  Souls + arcon ledgers are public; kept-memory provenance verified pure-arcon.
- **Backend:** isolated shard `ww_pdx_keep` (:8240), portland geography seeded (1318 places), doula off,
  no federation. **Pen (KEEP):** `anthropic/claude-haiku-4.5`. **Embedder:** `nomic-embed-text` (Windows
  Ollama via gateway) — drive vectors built for all 15 (recall/affect faithful, not neutral).
- **Cadence:** `record_run.py` round-robin `tick_once`, **15 residents × 30 rounds**, core-only (no
  doula/mirror/guild). Per-resident perception recorded at the world-client HTTP choke points.

## Result 1 — PARITY: the harness is faithful (the gate)
A same-pen replay (`replay_run.py`, claude-haiku) of KEEP's own recording **drains the recording with
0 misses / 0 leftover reads per resident** — every world read the resident makes on replay is served
from the recording, in order, and the recording is fully consumed. The real `perceive()` runs unchanged
on replay (substrate side-effects preserved); only the pen varies.
- *Bug found + fixed en route (logged for transparency):* an initial replay that reused KEEP's session
  id validated it via an extra boot `get_scene`, shifting the scene queue off-by-one (1 miss + 2 leftover
  /resident). Fix: replay bootstraps a FRESH session (matching KEEP's boot) and `ReplayClient` normalizes
  the session-id timestamp out of read paths. Parity then clean. (commit 7d98f43)
- **Recompute:** rehydrate a pristine arm, then
  `replay_run.py --arm-dir <pristine> --keep-dir <this run's source> --rounds 30` → expect 0/0.
  (Recordings here under `recordings/<name>.jsonl.gz`.)

## Result 2 — the curation surface is STARVED
New durable keeps during the 30-round KEEP run (final `kept_memory` minus the pristine-initial set;
both published under `kept_memory/` and `kept_memory_initial/`):

| | |
|---|---|
| new keeps, whole cohort | **6** |
| residents that kept anything new | **5 / 15** |
| keep rate | ~6 / 450 ticks ≈ **1.3%** |

Per-resident: 0,1,0,1,0,0,1,1,0,0,0,2,0,0,0. Keeps are deliberate by design ("most moments keep
nothing"), but at ~1.3%/tick the **memory-curation divergence measure is unpowered**: the per-resident
paired design (same resident, same experience, different pen) is impossible at ~0–2 keeps/resident, and
even a pooled read is ~6 vs ~6. Reaching ~10 keeps/resident would need ~750 ticks/resident — an
infeasible run at this rate.

## What this means (for the cross-check, not a verdict)
The **machine works** — perception-replay is faithful, the counterfactual ("same recorded life, swap the
pen") is executable and cheap to replay offline. The **measure** as drafted (`memory_kept` content
divergence) is starved at feasible scale. Open for Mr. Review: power it (much longer / curation-dense
run), switch the curation surface (edge/relationship-formation is more frequent than keeps — but this
cohort is relationship-sparse: 5 private directed carries), or redesign what "curation" we read. No
divergence number has been computed; we are deliberately not riding a verdict on 6 keeps.

## Provenance
`recordings/` = the per-resident perception streams (gzipped) — the cold evidence for parity. `kept_memory/`
+ `kept_memory_initial/` = the keep-harvest evidence. Live shard `ww_pdx_keep` is gitignored; this is the
durable public copy. Harness + recompute scripts: `ww_agent/scripts/pen_swap/` (in-repo).
