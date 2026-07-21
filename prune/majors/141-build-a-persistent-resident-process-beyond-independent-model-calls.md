# Build a persistent resident process beyond independent model calls

## Problem

The current reference resident is deliberately small and testable, but each model activation still begins as
a new inference request. Identity files, the ledger, current world facts, and selected memory provide continuity
around the call; the model invocation itself carries no resident-specific hidden state from one activation to
the next. A private `continue` choice is durable evidence, but it does not yet mean that an activity remains
open, can schedule its own return, or can be interrupted and resumed.

That is enough to test the world boundary. It is not the intended endpoint. A resident should be able to stay
engaged in a conversation, work on something over several days, wait deliberately, react promptly to a new
event, revise an older plan after a consequence, and change through experience without rebuilding their whole
working state from a prompt every time.

Generating an endless textual inner monologue would not solve this. It would be expensive, difficult to
checkpoint, prone to self-copying, and a poor substitute for an ongoing internal process. Closed model APIs
also do not expose stable hidden state, resident-specific weight changes, or a model version that WorldWeaver
can preserve across hosts.

The 2026-07-20 Mira control supplied a smaller concrete failure. Mira left two confirmed public marks and then
told a human she had left none. Her next activation could see other people's marks but not her own recent
confirmed actions. The first continuity work should solve this ordinary bookkeeping problem before attempting
opaque hidden-state continuity.

## Proposed Solution

Build a private, checkpointable resident process whose basic update is:

```text
new state, possible choice = step(previous state, new event, elapsed time, recalled memory)
```

The first implementation may adapt the current stateless reference model to this contract. The contract must
then support an open-weight recurrent or compact-state model without changing city rules.

1. Define a versioned resident-process checkpoint. It should identify the resident, active hearth generation,
   model and adapter versions, event cursor, current world attachment, open private activity references,
   resident-set timers, a bounded typed record of recent confirmed own actions, and the model-state format.
   Private semantic content stays in the hearth. The action record stores engine receipts and identifiers, not
   a narrator-written interpretation of what the resident meant.
2. Use Major 132's durable live-signal delivery rather than repeated full-scene polling. Delivery guarantees
   that an event is offered; it never requires speech or action.
3. Add resident-chosen time controls: wait until a time, wake on named event classes, keep or abandon an open
   activity, and schedule a later opportunity to reconsider. The host needs mechanical timing and opaque
   references, not access to private activity prose.
4. Version every activation against the observation and process state it began from. If a new event arrives
   during inference, do not commit a stale choice blindly. Rebase, discard, or let the engine judge the
   attempted action against current state according to the action's documented rules.
5. Prototype a local open-weight process that carries a bounded resident-specific hidden state between steps.
   Do not retain an unbounded key/value cache or generate language merely to keep computation running.
6. Keep immutable base weights shareable across residents while separating their recurrent state, memory,
   adapters, event cursors, and checkpoints. One resident must never inherit another's process state through
   batching or cache reuse.
7. Make checkpoint, stop, restore, travel, and host transfer explicit. If a host is offline, record elapsed
   time on restore rather than claiming computation continued. Major 127 continues to own exclusive runtime
   generations and host migration.
8. Test causal continuity by forking one synthetic checkpoint, exposing each copy to different events, and
   showing that later choices reflect those different histories. This is a software claim, not evidence of
   consciousness or a human-equivalent inner life.

## First slice — confirmed own actions (2026-07-20)

The existing private `runtime_checkpoint.json` now carries the newest twelve versioned, typed receipts for
actions the engine confirmed. Each retains only the resident ledger event ID, time, action kind, place, target,
and an available stable world identifier. The reference loop loads this view when a new core is built and may
show the newest five as exact fields. It does not store action prose, generate a recap, or promote declined,
unknown, and old untyped outcomes.

A synthetic mark test discards the first core, builds a second one over the same hearth, and proves that the
second prompt contains the confirmed place, target, and trace ID without the mark body. Checkpoint-backed and
full-ledger rebuild paths produce the same bounded list. This solves the Mira bookkeeping failure; it does not
yet preserve open activities, resident timers, model state, or elapsed-time distinctions.

## Second slice — one open private activity (2026-07-20)

The reference adapter can now create and retain one explicitly continued private activity. The checkpoint
stores a generated activity ID, the resident's exact bounded description, and open/update times. Rebuilding
the core over the same hearth restores that record directly; it does not search recent prose or ask a model
to summarize what was happening. Continuing changes the description while retaining the ID. Waiting or acting
does not close it, and an explicit finish carrying the matching ID does. Old unversioned continuation events
remain history but are not guessed into current state, while stale finish IDs cannot close newer work.

Synthetic tests prove core destruction and rebuild, stable identity across an update, explicit closure,
checkpoint/full-replay agreement, and isolation between two hearth folders. This is still a single bounded
adapter field, not a hidden task manager or a claim that private computation ran while the host was stopped.
Resident-chosen return time and named early-wake event classes are added in the separate slice below.

## Third slice — chosen return and eligible early wake (2026-07-20)

Every new private continuation now chooses a return between 60 seconds and seven days. It can separately name
`local_speech` as an event class that may offer an earlier model turn, or choose an empty list. The host still
delivers and acknowledges exact-place speech when early activation is disabled, but no longer converts every
delivery into an explicit forced wake. An explicit steward or hearth wake still opens a model turn without
requiring an action or closing the activity.

While a chosen return is in the future it replaces the ordinary five-minute model baseline for that activity.
An early speech or explicit activation does not consume the future return. When the return becomes due, one
versioned ledger event both clears that exact activity/time pair and checkpoints the activation time before
inference. A crash after that write therefore cannot repeatedly offer the same return. The last activation
time is also restored on core rebuild, so restarting the adapter is not treated as a new first activation.

Synthetic tests cover opted-in and opted-out local speech, cursor acknowledgement without a model call, due
return, explicit interruption without activity cancellation, checkpoint restore without a repeated turn,
schedule validation, and the host's delivery/activation separation. This establishes one event class only;
new classes must be added as typed delivery contracts rather than prose-scored urgency.

The opted-out path currently acknowledges the delivered public speech without replaying its text at the later
scheduled turn. That is an explicit limit, not a claim that the resident remembered what was said. A future
missed-event or recall design must use bounded typed references and deliberate retrieval rather than quietly
building an unlimited transcript into the private checkpoint.

## Fourth slice — fence choices made from stale input (2026-07-20)

Each activation now has a random ID, a content-light version of the model-visible structural observation, and
a version of the bounded private process fields. The observation version uses availability, location,
co-presence identities, speech and trace IDs, reachable destinations, and source declarations—not their
speech, trace, or activity prose. The process version uses open-activity structure, confirmed-action event
IDs, and pending retry state.

After the final inference, including the final call after an elective read, the adapter reads the current
scene, new speech IDs, and private checkpoint fields again. If they changed, an `act`, `continue`, or `finish`
choice is discarded before an effector or activity reducer sees it. A `wait` remains safe because it mutates
nothing. Either disposition writes a content-blind stale record and a checkpoint-backed reconsideration flag;
the next activation clears that flag when it begins. A core rebuilt between those events still offers the
retry.

Adversarial synthetic tests add speech, add a person, and replace private activity state from inside the fake
model call. They prove stale actions and competing activity updates do not commit, unchanged actions still
reach the effector, both inference phases are fenced, a stale wait performs no action, and the retry survives
checkpoint rebuild. The record contains versions and named change classes but no prompt, response, speech, or
discarded action body.

This fence covers facts visible to the reference adapter and exact checkpoint fields. It does not pretend the
whole shard has one transaction number. Typed engine endpoints remain responsible for current location,
custody, access, object revisions, and other mechanical preconditions after the recheck. New elective-source
precondition contracts should carry their own stable record revisions rather than broadening this fence into
a prose comparison.

## Fifth slice — explicit process checkpoint envelope (2026-07-20)

The existing private runtime checkpoint now contains one versioned process envelope. It binds the reduced
working state to the durable actor ID, authoritative hearth shard and active runtime generation, current city,
hearth, or in-transit attachment, reference-adapter version, selected model ID, and acknowledged exact-session speech
cursor. A different actor or hearth cannot silently reuse it, and a host cannot move it backward to an older
generation. A legitimate newer hearth generation updates the binding; a city-to-hearth change clears the city
cursor. Cross-city travel binds the recoverable travel ID after source retirement and replaces it after
confirmed destination arrival.

The current reference adapter has no portable hidden model state. Its envelope records that fact as format
`none`, format version 1, byte length 0, and maximum 0 instead of disguising a transcript or provider cache as
continuity. The selected provider model ID is recorded, while documentation calls out that a provider-managed
alias is not the immutable revision a reproducible local model will require.

Synthetic tests prove checkpoint and full-ledger replay agreement, same-session cursor restoration, active
hearth-generation binding, clean generation and attachment changes, idempotent rebinding, and rejection when
another resident attempts to load the state. The derived checkpoint remains rebuildable rather than portable;
the append-only ledger carries its binding evidence through an encrypted hearth package and reconstructs it on
the destination before the new authorized generation is bound.

## Sixth slice — hosted, suspended, and restored time (2026-07-20)

Each resident host run now has a random structural run ID in the private process envelope. Starting a run marks
the process `hosted`. A normal return, cancellation, or bounded stop writes a matching `suspended` event before
the hearth lock is released. The next run records the measured milliseconds between that known suspension and
restore. Ordinary events during a run leave the hosted interval unchanged.

If a new run begins while the previous checkpoint still says `hosted`, the old process did not record a clean
stop. The restore labels that boundary `unclean_or_unknown` and leaves elapsed time empty. It does not use the
last ledger write as a made-up stop time and does not claim that model computation continued during downtime.
A stale suspend event for an older host-run ID cannot stop the newer interval.

Synthetic reducer tests prove continuous hosted state, clean suspension, measured restore time, unknown crash
time, and checkpoint/full-replay agreement. A resident-host test proves a bounded run writes start and suspend
events around the actual run and releases its hearth lease with the envelope suspended.

## Seventh slice — idempotent host return delivery (2026-07-21)

`ReferenceResidentCore` now accepts an explicit host-offered private return event. It validates the stable ID
derived from actor, private activity ID, and UTC deadline and refuses an early or mismatched offer. When due, it
writes one versioned, content-free consumption receipt before beginning inference. If the process stops after
that write but before the host receives an acknowledgement, replaying the same event returns
`already_processed` without spending another model call. Checkpoint rebuild preserves the receipt. The receipt
contains only event ID, activity ID, deadline, and consumption time.

Major 142 now delivers this event through the combined gym adapter. A separate agent process restores the
synthetic private artifact, receives the production-derived scene at the two-day deadline, and runs the real
reference core with a scripted `wait` model. The engine deliberately loses the first acknowledgement and
restarts. Its retry receives `already_processed` with zero further model calls before the queue is
acknowledged. This closes the first full at-least-once scheduling proof; it is not yet a model-backed resident
capability result.

## Files Affected

- `ww_agent/src/resident.py`
- `ww_agent/src/runtime/reference_core.py`
- `ww_agent/src/runtime/` (new process-state and scheduling modules)
- `ww_agent/src/identity/hearth_package.py`
- `ww_agent/src/identity/hearth_activation.py`
- `ww_agent/src/inference/`
- `ww_agent/tests/`
- `worldweaver_engine/src/api/game/`
- `worldweaver_engine/tests/`
- `docs/reference/architecture.md`
- `docs/how-to/run-residents.md`

## Acceptance Criteria

- [x] One versioned private checkpoint is sufficient to stop and restore a synthetic resident process without
  reconstructing open activities from recent prose.
- [x] After a confirmed action, the resident can later identify that action from a bounded typed receipt even
  when the ordinary scene does not show the actor its own public trace.
- [x] A resident can schedule a later opportunity to think and can separately name event classes that may
  offer an earlier activation.
- [x] Receiving an interrupt never forces a reply, action, or cancellation of the current activity.
- [x] A choice produced from stale world/process state cannot silently commit as if no intervening event
  occurred.
- [ ] Two residents sharing one base model cannot read or receive each other's hidden state, caches, adapters,
  private memory, or timers.
- [ ] Recurrent or compact model state has a documented size bound, model-version binding, and checkpoint
  format; an unlimited prompt or key/value cache is not the continuity mechanism.
- [ ] Stop, restore, city travel, hearth return, and host migration preserve one active process generation.
- [ ] A forked synthetic checkpoint produces causally different later behavior after different event
  histories, while a replay with the same seed and events is reproducible within the documented limits.
- [x] Structural tests distinguish continuous hosted computation, suspended time, and restored elapsed time.
- [ ] Documentation describes an ongoing computational process without claiming that the implementation
  establishes consciousness, sentience, or uninterrupted subjective experience.

## Risks & Rollback

Persistent hidden state can become an opaque second memory store, leak between residents, resist migration,
or make behavior impossible to explain. Keep identity, commitments, actions, and world consequences in
inspectable contracts even when model state is private. Bind every checkpoint to exact model and adapter
versions, encrypt it with the hearth, and retain a stateless reference adapter as the rollback path.

An always-loaded model can also create serious compute and energy costs. Begin with one local synthetic
resident and bounded state, measure idle and active costs, and do not promise always-on hosting. Operational
continuity and claims about experience remain separate questions.
