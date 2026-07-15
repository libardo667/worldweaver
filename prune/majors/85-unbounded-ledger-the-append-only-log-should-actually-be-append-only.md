# Unbounded ledger — the append-only log should actually be append-only

## Progress (2026-07-14) — cold log and hot-read boundary landed; projection checkpoint remains

Three lockstep slices are committed in both substrate repositories:

- Stable `d1a787e` / WorldWeaver `1a71dba`: the cold `runtime_ledger.jsonl` now receives one append-mode
  write per event, never reloads/replaces the file for storage, and no longer contains `_MAX_EVENTS` or
  front-truncation. A regression test retains the first event after 10,050 later writes.
- Stable `06c3c18` / WorldWeaver `e9b71c3`: `load_runtime_reducer_events()` reads JSONL backwards and
  parses only the explicit 24-hour hot horizon. The horizon is six times the longest current reducer
  half-life (the four-hour baseline); an undersized window is rejected, and an unexpectedly dense horizon
  fails loudly rather than silently dropping evidence.
- Stable `6b4dd30` / WorldWeaver `02b1a8d`: afterimage, drive-nudge, baseline, arousal, grief, vital, and
  idle/ignition runtime reads use the bounded path. Complete-history audit, memory, and disorientation
  consumers deliberately remain on the cold log. A frozen representative ledger proves cold/hot equality
  for grief, arousal, baseline, afterimage, and (in WorldWeaver) vital.

The first three slices were also committed to Stable through `6b4dd30` under the ownership rule then in
force. That was the final lockstep change. WorldWeaver is now the sole canonical substrate owner; Major
76's sync tool and manifest have been retired, and all remaining checkpoint work lands here only.
WorldWeaver is green at 272 passed, 1 skipped.

**Still open:** `append_runtime_event()` still calls `rebuild_runtime_artifacts()`, which reduces the full
cold history and rewrites the projection family. The next slice is a versioned, atomic projection
checkpoint that advances from new events without scanning cold history; only after that lands is the
append+reduce cost flat and Major 85 complete.

## Decision and lineage

The runtime ledger (`ww_agent/src/runtime/ledger.py`) is described as the substrate's foundation:
*"the ledger is the only state; arousal, mood, grief, the slow self-model and the afterimage are all
`derive_*` reducers over an **append-only** event log."* But the log is not actually append-only — it
**front-truncates at `_MAX_EVENTS = 10000`** (`ledger.py:26,254`). The oldest events are silently
discarded. This nagged at the keeper for a while and surfaced concretely during Major 66 (the
relational-ledger verification): a long continuous run would only ever expose its last 10k events to
`reciprocity.py`, silently windowing the very ledger that work is trying to make complete.

- **Status:** in progress (2026-07-14, cold append and bounded short-timescale reads landed; projection
  checkpoint pending).
- **Honest scoping — grief is NOT currently broken.** An early hypothesis was that truncation
  amputates grief (the *undischargeable* integral). It does not, under current constants:
  `GRIEF_HALF_LIFE_SECONDS = 600` (`salience.py:59`) and these ledgers run ~1000 events / ~6 hours,
  so a 10k window spans ~2.5 days — any event old enough to truncate is already decayed to
  ~zero-weight in `derive_grief` (`salience.py:399-446`). The cap is *latently* dangerous, not
  *presently* wrong. This major fixes the latent hazard and the audit-completeness loss, and it must
  not regress grief or any long-horizon reducer.
- **Canonical in WorldWeaver.** The earlier `canonical-stable` rule was retired on 2026-07-14. Stable is
  implementation history, not an upstream working tree; all further ledger changes land only here.

## Problem

The append path is **O(n) per event**, which makes a run **O(n²)** total. `append_runtime_event`
(`ledger.py:1417-1433`) on *every* event: (1) `_load_events` reads and JSON-parses the **entire**
file; (2) appends one event; (3) `_save_events` re-serializes and rewrites the **entire** file,
trimming to `[-10000:]`; (4) `rebuild_runtime_artifacts` re-runs **all** reducers over the **entire**
history and rewrites five projection files. Each tick's cost grows with history. The 10k cap exists
to bound that cost — it is a **performance band-aid**, not a design choice (the source comment calls
it a "window… cheap insurance").

Two real harms follow from the band-aid:

1. **Audit/research history is destroyed, not decayed.** The append-only log is also the research
   record (`research/README.md`: "verify instead of trust"). On any run past 10k events per
   resident, the early relational edges (`in_reply_to`, addressing, co-presence once Major 66 Phase 2
   lands) are simply **gone** — a long-run reciprocity/convergence analysis silently sees only the
   tail. This is the harm Major 66 exposed.

2. **The cap is a *time-blind* guillotine over an unchecked invariant.** It drops the oldest N events
   regardless of timescale. It is safe today *only because* every reducer's memory is far shorter than
   the wall-clock a 10k window spans (arousal 300s, grief 600s, vital 1800s ≪ ~2.5 days). Nothing
   enforces `window_wallclock > longest_reducer_timescale`. A denser resident (a chatty burst
   compresses 10k events into hours), or any deliberately long-horizon reducer (the slow self-model;
   a future durable grief that outlives a 10-min half-life; a multi-day gate), silently loses its
   basis with **no error and no warning** — the most dangerous failure mode for a safety-relevant
   integral.

## Proposed Solution

Decouple the two consumers the cap conflates — the **runtime** (wants recent state, fast, bounded)
and **research/audit + long-horizon reducers** (want complete history) — so neither forces a
truncation on the other. Preferred shape: **hot/cold split with bounded/incremental reduction.**

1. **Cold log grows forever, O(1) appends.** The raw `runtime_ledger.jsonl` becomes truly
   append-only: open in append mode and write one line (no full reload, no full rewrite, no trim).
   This is the audit/research record.
2. **Runtime reduction reads a bounded tail, not the whole file.** Replace "re-reduce the entire
   history every tick" with a bounded read (last W events or last T seconds, whichever each reducer
   needs) plus, for anything genuinely long-horizon, a **persisted running value** (a small
   checkpoint the reducer advances incrementally rather than recomputing from the head). Grief,
   arousal, vital: bounded-tail is sufficient (their half-lives are minutes). The slow self-model /
   any durable integral: checkpoint.
3. **Make the window-vs-timescale coupling explicit.** Whatever bound the runtime uses, assert (in
   code or a test) that it exceeds the longest reducer timescale, so a future long-horizon reducer
   fails loudly at review rather than silently at runtime.
4. **Research tooling reads the cold log** unchanged (`research/probes/*` already read plain
   `runtime_ledger.jsonl` line-by-line — they simply stop being silently windowed).
5. **Migration:** existing already-truncated ledgers are accepted as-is (their pre-truncation history
   is already gone); the change is forward-only. No schema change to the event envelope.

Do **not** simply raise or remove `_MAX_EVENTS` — that keeps the O(n²) append and risks unbounded
memory/latency. The point is to change the cost model so unbounded history is cheap.

## Files Affected

- `ww_agent/src/runtime/ledger.py` — canonical WorldWeaver append, hot-read, checkpoint, and projection
  implementation.
- `ww_agent/src/runtime/salience.py` and any other `derive_*` reducer that currently assumes the full
  in-memory event list — switch to bounded-tail reads or checkpoints; preserve exact grief/arousal
  behavior on a frozen ledger (golden-output test).
- `the-stable/src/runtime/ledger.py` — historical lineage only; no further edits or synchronization.
- `research/probes/*` — no change expected; confirm they read the now-unbounded cold log correctly.

## Acceptance Criteria

- [ ] `append_runtime_event` appends in O(1) (one line, no full-file reload/rewrite, no trim);
      `_MAX_EVENTS` truncation is gone.
- [ ] A resident run of ≫10k events retains its earliest events on disk (audit completeness); a
      research probe over that ledger sees the full history, not a tail.
- [ ] `derive_grief`, arousal, mood, and the self-model produce **identical** output on a frozen
      pre-change ledger (golden test) — no behavioral regression from bounded reads/checkpoints.
- [ ] Per-tick append+reduce cost is bounded and flat as history grows (a 100k-event ledger ticks no
      slower than a 10k one) — the O(n²) is gone.
- [ ] An explicit assertion/test guards `runtime_read_window_wallclock > longest_reducer_timescale`,
      so a future long-horizon reducer fails loudly rather than silently.
- [x] WorldWeaver is the canonical substrate owner; no active sync manifest can overwrite or merge its
      ledger from `the-stable`.

## Risks & Rollback

- **Historical-source confusion.** Do not resume lockstep edits merely because an old Stable copy exists;
  WorldWeaver owns the substrate going forward.
- **Silent reducer regression.** Bounded-tail reads or checkpoints could change grief/self-model
  output subtly. Gate on a golden-output test over a frozen ledger before merge; grief especially
  (safety boundary) must be byte-identical.
- **Unbounded disk.** Truly-append-only means ledgers grow without limit. ~12 KB/1000 events, so a
  long run is still megabytes; add optional cold-log rotation/compaction (gzip old segments) if it
  ever bites — but never front-truncate the live reduction basis.
- **Rollback** = restore the `[-_MAX_EVENTS:]` trim in `_save_events`; readers degrade to the
  windowed behavior. Additive/forward-only, so rollback is a one-line revert.
