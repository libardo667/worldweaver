# Make ledger replay and working state reliable

## Problem

WorldWeaver's append-only resident ledger is the right place to record durable events, but its current
checkpoint and projection code can silently lose unresolved work.

`ww_agent/src/runtime/ledger.py` rebuilds complex state changes from only the newest 10,000 events. A route,
mail intent, research item, packet, or intent whose opening event is older than that window can disappear
without a closing event. Separate count caps retain the newest packets and intents regardless of status, so
completed noise can evict an older pending direct address. Packet and intent expiry fields are not enforced.

The write path also materializes five standalone projection JSON files, a route sidecar, staged mail Markdown
files, a checkpoint, and sometimes a runtime snapshot for each event. Most have no production reader. The
snapshot performs three complete-ledger reads on a queue change. Reducer builders consult the host wall clock,
so replay is not deterministic. The ledger append itself does not validate a partial tail or explicitly sync
the new record, and readers silently skip malformed data.

Synthetic fixtures reproduced lost open routes, eviction of pending direct-address packets, and loss of a
valid append after a truncated tail. The full evidence is in
[`ledger-replay-projections-and-durability.md`](../../research/audits/cognitive-core/ledger-replay-projections-and-durability.md).

This does not make reducers disposable. Deterministic software must own world and lifecycle state rather than
asking a language model to reconstruct it. The problem is that current, decaying, historical, and compatibility
state have been mixed together.

## Proposed Solution

1. Introduce one serialized ledger writer with tail validation, monotonic sequence numbers, newline-safe
   append, and an explicit flush/`fsync` durability contract.
2. Make reducer transitions pure with an injected `as_of` time. Use one authoritative event timestamp rather
   than mixing host time with payload clocks.
3. Advance all current lifecycle state incrementally from the checkpoint. Do not rebuild open work from an
   arbitrary event-count tail during normal operation.
4. Separate open-state indexes from decaying numeric reducers. Keep every unresolved route, packet, intent,
   mail item, research item, and action outcome until an explicit close or enforced expiry.
5. Apply bounds only to terminal history and decaying windows. Fail visibly if unresolved work exceeds an
   operational ceiling.
6. Give the runtime one current-state read API backed by a valid checkpoint plus any unapplied ledger tail.
   Move `CognitiveCore`, packet/intent queues, prompt construction, runtime status, and any temporary mirror to
   that API.
7. Remove unused standalone projection JSON files, `active_route.json`, and staged mail Markdown projections
   after a compatibility search and migration test. Replace the daily digest's snapshot dependency with a
   small on-demand operational status view.
8. Preserve complete cold history for research, audit, export, and migration. Never restore front trimming.
9. Make corruption visible and recoverable: quarantine a partial final record, fail loudly on middle-file
   damage, and record the byte offset and sequence involved.

Implement this in small slices. First lock in failing synthetic tests, then repair durability and checkpoint
semantics, converge readers, and only then delete dead shadows.

## Files Affected

- `ww_agent/src/runtime/ledger.py`
- `ww_agent/src/runtime/signals.py`
- `ww_agent/src/runtime/pulse_engine.py`
- `ww_agent/src/runtime/salience.py`
- `ww_agent/src/runtime/pulse.py`
- `ww_agent/src/runtime/memory.py`
- `ww_agent/src/runtime/resident.py`
- `ww_agent/src/identity/growth.py`
- `ww_agent/src/identity/hearth_package.py`
- `worldweaver_engine/scripts/daily_world_digest.py`
- `ww_agent/tests/`
- `docs/reference/architecture.md`
- `research/audits/cognitive-core/`

## Acceptance Criteria

- [x] A route, mail intent, research item, packet, and intent opened before more than 10,000 later events remain
      open until a named terminal event or enforced expiry.
- [x] Newer terminal history cannot evict an older unresolved packet or intent.
- [x] Packet and intent expiry uses an injected clock and writes an explicit terminal event.
- [x] The same prior state, event sequence, and `as_of` produce byte-identical reduced state.
- [x] Every accepted event has a monotonic sequence, and the checkpoint records the exact sequence and byte
      offset it includes.
- [x] A partial final record is detected and quarantined without losing the next valid append.
- [x] Corruption before the final record fails loudly instead of being skipped as missing history.
- [x] Concurrent or accidental second writers cannot interleave ledger records or acknowledge one sequence
      twice.
- [x] A normal event performs one ledger append and one checkpoint transition; it does not rewrite unconsumed
      projection or compatibility files.
- [ ] Normal runtime readers use the checkpoint/current-state API and do not repeatedly parse the complete
      cold ledger.
- [x] A full replay oracle agrees with the incremental checkpoint after every event in lifecycle and randomized
      sequence tests.
- [x] Complete cold history remains streamable for audit and research with no front truncation.
- [x] Migration/recovery tests cover existing ledgers and rebuild old derived files only when explicitly needed.

## Risks & Rollback

The main risk is changing reducer order or time semantics while trying to improve storage. Capture frozen
full-replay outputs and lifecycle fixtures before changing the implementation. Advance one typed reducer at a
time and compare the checkpoint against a full replay oracle after every event.

Removing sidecars can break an undocumented external script even though no repository reader exists. Announce
the migration, retain an explicit one-shot export command for one release, and remove files only after the
repository and operator-command checks pass.

A durability policy that calls `fsync` for every event may be slower on some disks. Measure group-commit or a
small write-ahead batch if necessary, but expose the acknowledged durability level. Do not trade visible
latency for silent record loss.

Rollback each slice independently: retain the old ledger format reader, rebuild the new checkpoint from cold
history, and restore a compatibility exporter if needed. Do not roll back to front truncation or bounded replay
of unresolved state.

## Progress

### 2026-07-20 — durable serialized append foundation

Checkpoint format 2 keeps existing JSONL ledgers readable by treating older records' physical order as their
implicit sequence. Every new accepted event carries an explicit increasing sequence. A short-lived file lock
covers sequence allocation, append, reducer transition, and checkpoint replacement, so two writers cannot
claim the same position. The event append and atomic checkpoint replacement are flushed to disk.

Cold replay now rejects blank, non-object, malformed, or mis-sequenced completed records. If a process left an
unterminated final fragment, the next writer saves those exact bytes beside the ledger before truncating only
that fragment and appending the next valid record. This completes the storage foundation, not the lifecycle
repair: the 10,000-event complex replay boundary and status-blind queue caps remain the next work.

### 2026-07-20 — unfinished work survives bounded replay

Reducer format 2 separates current lifecycle indexes from the bounded recent event view used by larger
semantic projections. Active routes, staged mail, queued research, and open packets and intents now advance
from the prior checkpoint for every append. A fixture places all five opening events before more than 10,000
neutral records, triggers the former destructive path, and proves that each remains until its named closing
event.

Packet and intent limits now reserve space for every unresolved item and trim only terminal history. Mail and
research limits reject an overloaded open queue instead of retaining only its newest members. This completes
the named lifecycle boundary. Explicit expiry events, pure replay clocks, current-state readers, and removal of
compatibility projection writes remain open.

### 2026-07-20 — explicit clocks, expiry, and current-state reads

Reducer format 3 removes wall-clock reads from full replay. Without an override, derived timestamps come from
the newest input event; tests can also inject one `as_of` time. Event append accepts the same kind of explicit
timestamp, so a virtual or runtime clock does not have to disagree with the event envelope.

Packet and intent queues now close due open items by appending `expired` status events at a caller-supplied
time. The resident core chooses one time at tick entry and uses it for both expiry passes and the rest of the
tick. A new current-state API returns the valid checkpoint and falls back to cold replay only when necessary;
packet, intent, route, mail, research, and operational snapshot reads now use that API. Remaining full-history
readers need individual classification as either legitimate history consumers or current-state callers.

### 2026-07-20 — one normal derived-state file

Normal append no longer writes five standalone projection JSON files, `active_route.json`, staged mail
Markdown, or `runtime_snapshot.json`. It appends the durable event and atomically replaces one checkpoint. An
explicit rebuild removes those legacy derivatives, while hearth packaging and Stable import continue to treat
them as disposable rather than resident history.

The daily operator digest reads queued intents from the checkpoint and falls back to a legacy runtime snapshot
only for an old folder that has no checkpoint intent state. Queue operations and expiry no longer refresh that
snapshot. A repository-wide reader search and focused migration tests cover this removal. The remaining work is
to classify direct cold-history readers and add a broader randomized incremental/full-replay oracle.

### 2026-07-20 — hot readers stop replaying a whole life

The ordinary cognitive tick now gets incubation aggregates and current cognitive nodes from the checkpoint.
Recent felt sense, anchor rate limiting, and voice samples use a bounded recent-event reader; decaying baseline
input uses the declared hot time window. Current salience reads the checkpoint directly. Runtime projection
format 4 records the first event time and aggregate event counts so the optional incubation calculation no
longer needs every historical record.

A deterministic shuffled lifecycle test compares the incremental checkpoint with a full replay after every
packet, intent, route, mail, and research transition. The remaining complete-history calls are now a short,
named list: resident attachment/travel crash recovery, legacy kept-memory reconciliation, explicit prediction
scoring, an anchor compatibility fallback, and operator/import scripts. Kept memory is the only remaining
ordinary duplicate-authority reader that needs consolidation before the current-state acceptance criterion is
complete.
