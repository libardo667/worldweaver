# Rebuild the letter system around persistent threads and readable inboxes

> **Re-baseline note (2026-07-14):** the `src/loops/mail.py` resident path named below is deleted.
> This major retains the human thread/inbox model and durable correspondence semantics; Major 72 owns the
> CognitiveCore send/perceive path and visibility edges. Implement the two against one shared thread
> contract, not by restoring the mail loop.

## Problem

The current letter system works, but it is too thin for humans and too weak as a
world channel.

Today on the human side:

- sending a letter gives a transient success message in
  `worldweaver_engine/client/src/components/LetterCompose.tsx`
- sent mail does not persist in an obvious thread view
- received mail is rendered as a flat newest-first list in
  `worldweaver_engine/client/src/App.tsx`
- there is no thread model, no search, no filter, no useful way to revisit a
  correspondence relationship over time

Today on the resident side:

- mail intents and mail events exist in `ww_agent/src/runtime/ledger.py`
- the mail loop in `ww_agent/src/loops/mail.py` can send and reply
- but the channel is behaviorally weaker than local chat and not yet treated as
  a first-class continuity surface

This creates two problems:

- the player experience of letters feels underbuilt and forgetful
- the runtime treats correspondence as a side lane instead of a durable social
  medium

If letters are going to matter to humans and AI alike, they need stronger UX,
stronger persistence, and clearer thread semantics.

## Proposed Solution

Rebuild letters as a persistent correspondence system rather than a one-off send
form plus inbox dump.

### Phase 1 - Introduce explicit mail threads

Define a thread model for correspondence.

- one thread per pair or bounded conversation context
- thread view should contain sent and received messages in order
- thread metadata should include participants, last activity, unread state, and
  maybe status such as draft / awaiting reply

For AI behavior, thread identity should also be visible in resident reduced
state.

### Phase 2 - Improve human mail UX

Replace the current "send and it disappears" experience with persistent
correspondence surfaces.

- sent messages remain visible in the UI
- inbox becomes a thread list, not a flat dump
- individual threads are openable and scrollable
- unread/read state is explicit
- search and basic filtering are supported

This should feel closer to a readable mailbox and less like a hidden debug form.

### Phase 3 - Strengthen mail as a resident behavior lane

Residents should treat letters as durable social obligations.

- incoming mail should create correspondence pressure that survives local chat
- residents should be able to reply, defer, archive, or intentionally ignore
- outgoing letters should emerge from real concerns, not only generic politeness
- mail thread state should be visible in reduced state and subjective facts

### Phase 4 - Unify human and AI mail semantics

Humans and residents should participate in one correspondence model.

- the same thread identity should be visible to both sides where appropriate
- travel and actor identity work should not break correspondence continuity
- thread participants should resolve through actor identity, not only transient
  session identity

### Phase 5 - Prepare letters for slower-burn world life

Letters should become the natural lane for:

- delayed replies
- follow-up after meetings
- invitations and plans
- unresolved distance relationships
- cross-shard continuity later on

That means the letter system has to be a first-class continuity surface, not
just a niche extra.

## Files Affected

- `worldweaver_engine/client/src/App.tsx`
- `worldweaver_engine/client/src/components/LetterCompose.tsx`
- `worldweaver_engine/client/src/api/wwClient.ts`
- `worldweaver_engine/client/src/styles.css`
- `worldweaver_engine/src/api/game/world.py`
- `worldweaver_engine/src/models/__init__.py`
- `worldweaver_engine/src/services/federation_pulse.py`
- `ww_agent/src/loops/mail.py`
- `ww_agent/src/runtime/ledger.py`
- `ww_agent/src/loops/slow.py`
- `ww_agent/tests/test_loop_packets.py`
- `worldweaver_engine/tests/api/*mail*`
- `prune/majors/37-formalize-actor-scoped-cross-shard-travel-and-runtime-transfer.md`
- `prune/majors/38-rebalance-resident-channel-salience-across-local-chat-mail-and-city-context.md`

## Acceptance Criteria

- [ ] Players can see persistent sent and received correspondence in an openable thread view
- [ ] The inbox is no longer a flat newest-first dump with no thread structure
- [ ] Thread unread state is visible and clearable
- [ ] Players can search or filter correspondence in a basic but useful way
- [ ] Residents treat incoming letters as durable reply obligations rather than weak background noise
- [ ] Mail thread identity is visible in resident reduced state and survives local-chat churn
- [ ] Human and AI correspondence semantics align around the same thread model
- [ ] The system remains compatible with later actor-scoped cross-shard mail continuity

## Risks & Rollback

- A full thread model can add schema and API complexity quickly. Roll back by
  staging with a derived thread view over existing messages before making
  threads fully canonical.
- If mail becomes too prominent, the world may skew toward inbox play instead of
  scene life. Roll back by keeping mail a slower-burn lane rather than an urgent
  interrupt channel.
- UI thread views can become cluttered if they expose raw filenames or debug
  artifacts. Roll back by keeping the player-facing model actor/thread centric.
