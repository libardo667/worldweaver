# Ledger replay, projections, and durability

Status: code and synthetic-fixture audit, 2026-07-19. No resident prose or live resident state was read.

## Plain result

The event log and reducer pattern are worth keeping. They give WorldWeaver a way to record what happened and
derive current state without asking a language model to manage the world's facts. The surrounding
implementation is not yet reliable enough to be that foundation.

The current code mixes four different jobs in one module:

- durable event storage;
- current open work, such as a route or pending message;
- short-lived numerical signals that legitimately use a time window;
- debug and compatibility files.

It then applies count limits and replay shortcuts across those jobs as if they had the same lifecycle. They do
not. A decaying signal may safely ignore old evidence. An unfinished route cannot safely disappear because its
opening record is old. A handled packet may be dropped from a working index. A pending direct address may not.

The result is a system that is append-only at the file level while still capable of silently forgetting its
current work.

## What should be preserved

Several choices are sound:

- `runtime_ledger.jsonl` retains the complete cold history instead of front-trimming it;
- the checkpoint records an exact ledger byte offset and rejects itself when that offset no longer matches;
- JSON checkpoint writes use a temporary file, `fsync`, and atomic replacement;
- event facts and derived state are conceptually separate;
- short-lived reducers have an explicit time horizon and fail loudly when the horizon becomes too dense.

The repair should simplify and finish this design, not replace state reduction with model-authored state.

## One append currently performs many unrelated writes

`append_runtime_event()` writes one JSONL record, then updates a reduced state. That update writes:

1. `active_route.json` or removes it;
2. every staged `intents/intent_*.md` mail file and removes obsolete ones;
3. `runtime_projection.json`;
4. `subjective_projection.json`;
5. `memory_projection.json`;
6. `subjective_facts.json`;
7. `cognitive_projection.json`;
8. `runtime_checkpoint.json`.

Packet and intent queue operations then write `runtime_snapshot.json` as another pass. That snapshot calls
three helpers which each read and reduce the complete cold ledger separately
(`signals.py:33-36, 296-302, 380-402, 418-424`).

Repository-wide reference searches found no production reader for the five standalone projection JSON files,
`active_route.json`, or the staged mail Markdown files. Live cognitive code reduces events into an in-memory
`ResidentReducedState`; the runtime checkpoint already contains the same projections. Hearth packaging also
classifies these files as rebuildable. The source comment saying the route and mail sidecars are “still read
directly by loops” is false (`ledger.py:1950-1953`).

`runtime_snapshot.json` does have one production reader, the daily world digest. It should remain only until
that operational reader uses a small, explicit status API. It should not require three full-history reads on
every queue change.

This is accidental write amplification, not useful redundancy.

## A 10,000-event replay can erase current state

For event types classified as complex, the append path ignores most of the current checkpoint state. It
rebuilds packets, intents, active route, active mail intents, research queue, and all semantic projections from
only the newest 10,000 ledger events (`ledger.py:1921-1947`). It preserves the checkpoint only for aggregate
runtime counts.

That makes unfinished work depend on event density:

- an active route opened more than 10,000 events ago disappears even without a `cleared` event;
- a staged mail intent can disappear even without sent, declined, or suppressed evidence;
- a queued research item can disappear even without a pop;
- an old pending intent or packet can disappear without a terminal status.

A synthetic reproduction created an active route followed by 10,000 neutral records and built a valid
checkpoint. The route was present. Appending one ordinary `session_state_observed` event selected the complex
path. The next checkpoint reported 10,002 total events but `active_route: null`.

```text
event_count_before: 10001
active_route_before: orchard via bridge
active_route_after_complex_append: null
checkpoint_event_count_after: 10002
```

This is not a rare corrupt-checkpoint recovery case. Session, grounding, ambient pressure, movement, speech,
action, research, route, and mail events all select this path during normal operation
(`ledger.py:43-69, 2047-2063`).

## Working-list limits discard unresolved items

The packet reducer sorts all known packets and keeps the newest 200 without considering status
(`ledger.py:492-509`). The intent reducer likewise keeps the newest 100 before priority sorting
(`ledger.py:516-542`). Active mail and research lists apply the same kind of count cap after reconstructing
open items (`ledger.py:575-634`).

A second synthetic fixture emitted one old pending direct-address packet and 200 newer packets already marked
observed. Reduction retained 200 records, discarded the pending direct address, and reported zero pending
packets.

```text
emitted_packet_count: 201
projected_packet_count: 200
old_pending_direct_packet_retained: false
projected_pending_count: 0
```

This is especially serious because `StimulusPacketQueue.mark_status()` can only update a packet it can first
find in that bounded projection. Once evicted, the pending packet cannot be observed, ignored, or expired
through the queue API (`signals.py:380-410`). The constructor's configurable `max_items` value is stored but
never used; the reducer's module constant wins. `expires_at` is parsed and serialized for packets and intents,
but neither queue enforces it.

A safe bound must be lifecycle-aware. Terminal history may be sampled or dropped from a working view. Every
unresolved item must remain indexed until an explicit terminal event or enforced expiry closes it. If the
number of unresolved items exceeds an operating limit, the system should report overload rather than erase
the oldest work.

## The reducer is not a deterministic replay function

`reduce_runtime_events(events)` looks like a pure fold, but its builders call the host wall clock for
`updated_at` (`ledger.py:697, 963, 1053, 1345, 1633`). The same frozen event list therefore produces different
JSON at different times.

Top-level event timestamps are also always taken from the live host clock inside `append_runtime_event()`
(`ledger.py:2048-2052`), while callers sometimes place a separate logical timestamp inside the payload. Some
reducers use the event envelope and others use payload-specific fields. The hot reader windows by the envelope
timestamp. This makes deterministic virtual-time replay harder and allows one logical moment to carry several
different clocks.

Derived `updated_at` should be based on an explicit `as_of` supplied to the reducer or on the newest input
event. Event creation should accept one authoritative timestamp from the runtime clock. A replay should never
consult the machine's current time implicitly.

## The append-only file is not crash-safe enough to be the authority

The append helper writes to a text file and closes it without an explicit flush and `fsync`
(`ledger.py:484-489`). There is no tail validation before the next append. Readers silently skip malformed
JSON lines and turn any file-read exception into an empty history (`ledger.py:368-387`). Reverse readers also
silently skip malformed records.

A synthetic crash-tail fixture wrote one valid record and one truncated JSON record without a final newline,
then called the normal append helper. The new valid JSON was joined directly onto the truncated fragment. The
loader silently skipped the combined line, losing both the damaged record and the new append.

```text
records_physically_attempted: 3
records_loaded: 1
new_append_lost_with_truncated_tail: true
```

The ledger also has no serialized writer lock or monotonic sequence number. The normal resident lease reduces
the likelihood of two resident hosts writing at once, but it does not make the storage primitive safe for
maintenance tools, migrations, or an accidental second process.

For a canonical history, malformed data must be visible. Startup should distinguish and quarantine a damaged
final record from corruption in the middle. Appends should be serialized, newline-safe, flushed, and synced
according to a declared durability policy. Every accepted event should receive an ordered sequence number so
checkpoints can prove exactly what they include.

## Why the existing tests passed

The ledger tests are not worthless. They verify cold-log retention, byte-offset invalidation, checkpoint
version checks, short-horizon numerical agreement, and a bounded cost ceiling. They failed to test the
semantic boundary introduced by the optimization.

- The 10,051-event retention test replaces `rebuild_runtime_artifacts()` with a no-op. It correctly proves
  that the JSONL file is not front-trimmed, but exercises none of the checkpoint or projection path
  (`test_ledger.py:15-29`).
- The bounded packet test creates 250 packets that are all already observed, then explicitly requires the
  first 50 to disappear. That is safe for its fixture and silently establishes the unsafe algorithm for a
  mixed pending/terminal queue (`test_ledger.py:172-193`).
- The complex-update oracle test uses only two events. At that size, “newest 10,000” and “complete history”
  are the same input, so agreement cannot test what happens at the boundary (`test_ledger.py:289-314`).
- The 100,000-event timing test writes the same event, including the same event ID, 100,000 times and manually
  constructs a checkpoint whose aggregate count says 100,000. It proves that the path's wall time is capped
  by a 10,000-record replay. It does not prove that the capped replay preserves current state
  (`test_ledger.py:317-355`).
- The corruption recovery test damages `runtime_checkpoint.json`, not `runtime_ledger.jsonl`. It proves the
  disposable cache can be rebuilt from a good ledger, not that the authoritative ledger survives a damaged
  tail (`test_ledger.py:147-169`).
- The test named “atomically” verifies version fields, final byte offset, and absence of leftover temporary
  files after a successful write. It does not interrupt replacement or verify the ledger/checkpoint pair as
  one transaction (`test_ledger.py:106-121`).
- Tests frequently freeze `_utc_now_iso()` or remove `updated_at` before comparison. Those are reasonable
  fixture techniques, but they also hide that the public reducer contract itself reads the live clock.

The general lesson is to test lifecycle invariants across the exact optimization boundary. Comparing a fast
path against a full replay is strong only when fixtures include old still-open state, every terminal
transition, mixed statuses, and corrupted storage.

## The target shape

The smallest coherent design is:

1. **One durable event writer.** It assigns a monotonic sequence, validates or repairs only a partial tail,
   serializes writers, appends one newline-delimited event, and durably flushes before acknowledging it.
2. **One pure reducer contract.** `fold(previous_state, event, as_of)` has no hidden wall-clock reads. Different
   typed reducer components can exist, but their inputs and clocks are explicit.
3. **One checkpoint as the rebuild cache.** It contains current lifecycle state, reducer accumulators, schema
   versions, and the exact ledger sequence/offset it covers. Each event advances it from its previous state;
   normal complex events do not reconstruct current work from an arbitrary tail.
4. **Separate durable and decaying state.** Pending packets, routes, correspondence, research, object actions,
   and other open lifecycles remain until closed. Arousal-like numerical traces may use an explicit time
   horizon because decay is their actual contract.
5. **One current-state read API.** Cognitive code, queues, mirrors, and operations tools request the checkpoint
   plus any unapplied tail through one interface. They do not independently rescan the cold ledger.
6. **No unowned shadows.** Delete the five standalone projection JSON files, route sidecar, and mail-intent
   Markdown projection after verifying migration compatibility. Replace `runtime_snapshot.json` with an
   on-demand, content-blind operational view.
7. **Cold history stays complete.** Research and migration tools may stream all events. A repair must not bring
   back front truncation or make a model responsible for deterministic world state.

## Required tests before calling the ledger reliable

- A route, mail intent, research item, packet, and intent opened before more than 10,000 later events remain
  open until their named terminal event.
- Terminal history can be bounded without evicting any unresolved item.
- Queue constructor limits either work as declared or are removed.
- Packet and intent expiry is applied using an injected clock and produces a terminal event.
- The same events, prior state, and `as_of` produce byte-identical reduced state.
- A partial final record is detected and quarantined; the next append remains readable.
- Corruption in the middle of a ledger fails loudly with the byte offset and does not become missing history.
- Two writers cannot interleave or acknowledge the same sequence.
- After a successful append, one checkpoint read agrees with a complete replay oracle.
- A normal queue change performs one append and one checkpoint transition, not several full-history reads and
  nine materialized-file writes.

These are ordinary database and state-machine requirements. They do not depend on whether any current
cognitive metaphor is retained.
