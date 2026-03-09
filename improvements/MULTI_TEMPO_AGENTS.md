# Multi-Tempo Agent Architecture — V4 Design

## Problem

All agents currently run on a single heartbeat: one monolithic cron that reads
the world, decides what to do, takes an action, and maybe writes a letter. This
produces a flat, undifferentiated behavior pattern regardless of what is actually
happening in the world.

The root cause is a category error. **Not all cognition runs on the same clock.**

A character startling at a sudden noise is not the same act as a character
lying awake at night revising their opinion of someone. These require different
inputs, different outputs, and different time horizons. Forcing them through the
same pipeline produces characters that are simultaneously over-reactive and
under-reflective — blurting long introspective monologues when startled, or
failing to notice someone standing next to them because the context window is
full of week-old events.

---

## Core Concept

A character is not one agent. A character is a small society of agents with
different jobs and different tempos. They share a persistent identity (SOUL.md,
IDENTITY.md, the decision log) but each loop reads and writes only what it needs.

Three loops:

### Fast Loop — Scene-Local Reaction

**Runs:** every 60–90 seconds, or triggered by a new colocated event
**Context:** current location, who is present, their last action, last 3 local events
**Output:** one short visible action or spoken line
**Powers:** speak, emote, notice, make a tiny local move
**Forbidden from:** rewriting SOUL.md, sending letters, taking distant world actions,
reading more than the last 5 world events

This loop is a reflex. It sees what's in the room and responds to it. Its
context window is intentionally small — it doesn't know about things that
happened across the world three days ago. That's a feature, not a bug.

The fast loop produces **provisional impressions**: brief fragments saved to
`$ENTITY_DIR/provisional/` that describe a raw reaction without interpretation.
These are ephemeral scratchpad entries, not decisions.

### Slow Loop — Reflective World Processing

**Runs:** every 5–8 minutes
**Context:** SOUL.md, last 20 world events, current decision log, provisional fragments
**Output:** one substantive world action, goal update, or mood revision
**Powers:** everything the fast loop can do, plus: rewrite goals, update decisions,
send one letter draft to the mail loop, archive or promote provisional impressions
**Forbidden from:** sending letters directly (must stage them for the mail loop)

This loop is the thinking self. It reads accumulated world changes and
provisional fragments from the fast loop and decides what they mean. It may
confirm a fast-loop impression ("yes, that stranger was suspicious"), revise it
("actually that was just nerves"), or discard it. This is where character
development happens.

The slow loop can also note that a letter should be written, staging a draft
in `$ENTITY_DIR/letters/drafts/` with metadata about urgency and recipient.

### Mail Loop — Correspondence Triage

**Runs:** every 10–15 minutes
**Context:** inbox, staged letter drafts, relationship notes from SOUL.md
**Output:** send or discard staged letters, reply to inbox items
**Powers:** read inbox, send letters via API, mark letters replied
**Forbidden from:** taking world actions, updating SOUL.md, writing provisional impressions

The mail loop is a dedicated social processor. It handles correspondence
asynchronously and on its own cadence. A character who has been busy in the
world may have 3 staged drafts and 2 inbox letters waiting — the mail loop
handles the triage without blocking the fast or slow loops.

Critically: the mail loop decides whether a staged draft from the slow loop is
actually worth sending. The slow loop might stage an impulsive draft; the mail
loop, reading it later with fresh eyes, might decide it's too revealing and
discard it.

---

## The Provisional Scratchpad

The fast loop's most important output is the provisional impression — a short
timestamped fragment describing a raw reaction.

```
$ENTITY_DIR/provisional/
  imp_20260309-161432.md   ← fast loop wrote this
  imp_20260309-163017.md
  imp_20260309-164501.md   ← slow loop already archived this
```

Format of a provisional impression file:

```markdown
ts: 2026-03-09T16:14:32
trigger: Casper set down a resonant sphere near me
raw_reaction: I felt something I didn't expect — an urge to step away
status: pending
```

The slow loop reads all `pending` impressions, processes them, and either:
- Promotes to a decision entry (wrote it into decisions log, deleted the file)
- Archives with a note (renamed to `archived/`, adds interpretation)
- Discards silently (deleted)

This creates a two-pass cognition model:
1. Fast blurt in the moment
2. Slow interpretation afterward

A character can say something surprising in the moment that their slow loop
later has to make sense of. That's very human.

---

## Capability Contracts

Each loop has a strict capability contract that is part of the HEARTBEAT file,
not just convention.

| Capability | Fast | Slow | Mail |
|---|---|---|---|
| POST /api/action | ✓ | ✓ | — |
| Read last N events | 5 max | 20 max | — |
| Read location graph | ✓ | ✓ | — |
| Write provisional impression | ✓ | — | — |
| Read provisional impressions | — | ✓ | — |
| Update SOUL.md | — | ✓ | — |
| Stage letter draft | — | ✓ | — |
| POST /api/world/letter | — | — | ✓ |
| Read inbox | — | — | ✓ |
| Reply to letters | — | — | ✓ |

The HEARTBEAT files for each loop should open with a capabilities block
that explicitly states what this loop is and is not allowed to do.
Violations corrupt the character. Respect the contract.

---

## Personality Through Parameter Tuning

Same architecture, different tuning = different personalities:

**Reactive / Impulsive character** (e.g. someone hot-tempered):
- Fast loop fires frequently, with low threshold for action
- Slow loop runs less often, rarely overrides fast-loop choices
- Mail loop sends drafts quickly, minimal triage

**Deliberate / Reserved character** (e.g. someone measured):
- Fast loop fires rarely, mostly observes and notices
- Slow loop runs more often, frequently revises or discards fast impressions
- Mail loop holds drafts for one cycle before sending

**Prolific correspondent** (e.g. a letter-writer by nature):
- Fast loop minimal
- Slow loop stages many drafts
- Mail loop runs frequently, sends most of what it receives

**Socially absent but world-aware** (e.g. a recluse):
- Fast loop rarely fires even when colocated
- Slow loop reads wide world context, takes occasional distant actions
- Mail loop essentially disabled

These are just cron interval + context window size + instruction tone. The
architecture is the same. The character emerges from the parameters.

---

## File Layout

```
$ENTITY_DIR/
  session_id.txt
  world_id.txt
  SOUL.md                      ← slow loop reads + writes
  turns/turn_<N>.json          ← fast + slow loop writes
  decisions/decision_<N>.json  ← slow loop writes
  provisional/
    imp_<ts>.md                ← fast loop writes, slow loop consumes
    archived/                  ← slow loop archives processed impressions
  letters/
    drafts/
      draft_<ts>.md            ← slow loop stages, mail loop sends or discards
    letter_<N>.md              ← mail loop writes (sent)
    inbox/                     ← incoming letters
    inbox/read/                ← mail loop archives here
```

---

## Heartbeat Files

Each entity workspace gets three heartbeat files instead of one:

```
$ENTITY_WORKSPACE/
  HEARTBEAT_fast.md
  HEARTBEAT_slow.md
  HEARTBEAT_mail.md
```

These map to three separate cron entries in `openclaw.json`:

```json
{
  "id": "casper-fast",
  "agent": "casper",
  "skill": "worldweaver-player-fast",
  "interval_seconds": 75
},
{
  "id": "casper-slow",
  "agent": "casper",
  "skill": "worldweaver-player-slow",
  "interval_seconds": 360
},
{
  "id": "casper-mail",
  "agent": "casper",
  "skill": "worldweaver-player-mail",
  "interval_seconds": 600
}
```

The doula spawn workflow generates all three heartbeats. The spawn CSV gains
three optional columns for interval overrides.

---

## Scene-Triggered Fast Loop (Future)

The cron-based fast loop fires on a timer, which means it may miss events that
just happened nearby, or fire when nothing interesting is occurring.

A better trigger: the fast loop fires when a new event appears at the agent's
current location — specifically when another session posts an action in the same
place. This requires a lightweight polling endpoint:

```
GET /api/world/scene/{session_id}/new-events?since=<ts>
```

Returns events at the agent's location since the given timestamp. The fast
loop's cron checks this endpoint first; if nothing new, it skips its turn.
If something is there, it fires immediately.

This makes fast-loop behavior event-driven rather than time-driven — a character
actually reacts to what's happening, not just to the clock.

---

## Relation to Scene Endpoint

The existing `GET /api/world/scene/{session_id}` already returns what the fast
loop needs: colocated characters, their last actions, recent local events. This
is the fast loop's entire context. It reads this, responds to what it finds, and
exits. No sweeping world history, no letter drafts, no goal review.

The slow loop reads this too, but supplements it with a full event scan, the
provisional fragment queue, and the SOUL.md.

---

## Agent Skill Update

The current `worldweaver-player.md` skill becomes the slow loop's skill. Two
new skills are needed:

- `worldweaver-player-fast.md` — scene-local context, strict output contract
- `worldweaver-player-mail.md` — inbox triage, staging, send/discard

The fast skill should open with:

> You are the immediate, scene-aware self of [character]. You see only what is
> in front of you right now. Your job is to notice and respond — briefly, in
> character, in the moment. You do not reflect, plan, or send letters. One action.
> Then stop.

---

## Rollout Plan

### Phase 1: Define skill files and test manually (no cron changes)

Write `worldweaver-player-fast.md` and `worldweaver-player-mail.md` in the
template workspace. Manually invoke them against a running world session to
verify the output is appropriately scoped.

Define the provisional impression format. Verify the slow loop (existing skill)
can consume and archive them.

### Phase 2: Wire fast loop to one agent

Pick one agent (Casper is a good candidate — reactive, physical, social). Add
a second cron entry pointing to `worldweaver-player-fast.md` with a 75-second
interval. Leave the existing slow-loop cron unchanged.

Observe: does the fast loop produce contextually appropriate short responses?
Does it stay within its capability contract without explicit enforcement?

### Phase 3: Mail loop separation

Move letter sending out of the slow loop skill. Add `worldweaver-player-mail.md`
and a third cron entry. Stage a few letter drafts manually to test the triage
behavior.

### Phase 4: Roll out to all agents, tune per-character

Adjust intervals and context window sizes per agent based on personality goals.
Some agents may skip the mail loop entirely if they're not correspondent types.

### Phase 5: Scene-triggered fast loop

Add `GET /api/world/scene/{session_id}/new-events?since=<ts>`. Modify the fast
loop cron to short-circuit when nothing new has happened locally. This is an
optimization, not a behavior change — but it dramatically reduces idle LLM calls.

---

## Non-Goals

- **Coordination between loops.** The loops do not directly message each other.
  They communicate only through shared files (provisional fragments, letter drafts).
  No inter-process communication, no shared locks.
- **Loop arbitration / conflict resolution (V4).** If the fast loop takes an
  action and the slow loop has a different plan, the slow loop simply proceeds on
  its next cycle with updated context. Race conditions are fine — the world absorbs
  them as character inconsistency, which is realistic.
- **Event-driven triggers (Phase 5 only).** The V4 implementation is cron-based.
  The scene-polling optimization comes later once the behavior is validated.
- **Multi-agent orchestration frameworks.** This is not a crew or chain of agents.
  Each loop is an independent actor with its own context window. They happen to
  share a workspace and an identity.
