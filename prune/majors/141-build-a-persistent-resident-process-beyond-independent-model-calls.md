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

## Proposed Solution

Build a private, checkpointable resident process whose basic update is:

```text
new state, possible choice = step(previous state, new event, elapsed time, recalled memory)
```

The first implementation may adapt the current stateless reference model to this contract. The contract must
then support an open-weight recurrent or compact-state model without changing city rules.

1. Define a versioned resident-process checkpoint. It should identify the resident, active hearth generation,
   model and adapter versions, event cursor, current world attachment, open private activity references,
   resident-set timers, and the model-state format. Private semantic content stays in the hearth.
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

- [ ] One versioned private checkpoint is sufficient to stop and restore a synthetic resident process without
  reconstructing open activities from recent prose.
- [ ] A resident can schedule a later opportunity to think and can separately name event classes that may
  offer an earlier activation.
- [ ] Receiving an interrupt never forces a reply, action, or cancellation of the current activity.
- [ ] A choice produced from stale world/process state cannot silently commit as if no intervening event
  occurred.
- [ ] Two residents sharing one base model cannot read or receive each other's hidden state, caches, adapters,
  private memory, or timers.
- [ ] Recurrent or compact model state has a documented size bound, model-version binding, and checkpoint
  format; an unlimited prompt or key/value cache is not the continuity mechanism.
- [ ] Stop, restore, city travel, hearth return, and host migration preserve one active process generation.
- [ ] A forked synthetic checkpoint produces causally different later behavior after different event
  histories, while a replay with the same seed and events is reproducible within the documented limits.
- [ ] Structural tests distinguish continuous hosted computation, suspended time, and restored elapsed time.
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
