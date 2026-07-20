# Build a private steward operations surface

## Status

The ordinary commons client is now deliberately free of shard-wide resident telemetry. Useful operating
signals still exist in the old combined client and backend, but they have not been reduced to a separate,
authenticated product with a written privacy boundary.

The old “semi-public observatory” and “player shadow” proposals are rejected. Read-only surveillance is
still surveillance, and a federation-held AI copy of a human is not part of the current resident model.

The 2026-07-19 CognitiveCore audit found a more urgent backend contradiction. Every city resident currently
copies full reduced private state into city session variables once a minute. General game routes then allow an
unauthenticated caller to read or arbitrarily patch those variables; public world routes reveal the needed
session IDs. Legacy identity growth, session cleanup, duplicate pruning, and whole-world reset are also exposed
without the intended player, resident, node, or steward authority. Exact prompt capture is default-on and
unbounded. Agent bootstrap, leave, and travel likewise have no resident/host credential: checks that protect a
human-owned session accept an anonymous request when the session belongs to a resident. See
[`private-state-data-custody-and-operator-boundary.md`](../../research/audits/cognitive-core/private-state-data-custody-and-operator-boundary.md).

This is now a precondition rather than a later UI task: remove the private mirror and secure the underlying API
before building any steward screen or interpreting another public resident run.

## Goal

Give a steward enough information to keep their own node healthy without giving them a dashboard for
watching or shaping residents.

## Build next

1. Write a field-by-field access table before building the UI. For every value, name the operating need,
   role, retention period, audit record, and safer aggregate alternative.
2. Start with node health, service readiness, storage, database migration, federation reachability,
   inference availability, aggregate cost, backups, and failed jobs. Include content-blind counts of scene and
   source availability, stale observations, model request/completion/validation outcomes, retries, pending
   delivery packets, and unknown action outcomes.
3. Add resident-level runtime detail only when a concrete incident cannot be handled with an aggregate or
   resident-supplied report.
4. Require local authentication and an explicit steward role. Record access to sensitive views.
5. Reuse old client code only after it passes the access table; delete the rest.
6. Keep City Studio separate. City authoring before habitation does not grant access to resident state.

## Never show or control

- prompt or response text;
- private ledger, memories, beliefs, letters, hearth files, or workshop contents;
- resident preference, reward, personality, growth, or behavior-target controls;
- shard-wide live prose feeds presented as operations data;
- a public roster with rest reasons, wake estimates, private goals, or runtime queues.

An emergency diagnostic that genuinely needs sensitive data must be a separate, time-bounded, audited
procedure rather than a permanent dashboard field.

## Acceptance criteria

- [ ] A reviewed access table defines every steward-visible field and its retention.
- [ ] The surface is separately authenticated and unavailable to ordinary participants and observers.
- [ ] A steward can diagnose node health, storage, migrations, federation, inference, backups, and failed
  operations without reading resident prose.
- [ ] The surface distinguishes attempted model calls from valid completions and absent observations from
  unavailable or stale ones.
- [ ] Pending/observed packet counts and unknown action outcomes are visible without exposing packet content.
- [ ] Sensitive access is time-bounded and audited where it cannot be avoided.
- [ ] No control can alter resident identity, preferences, cognition, or private history.
- [ ] The public client imports no steward telemetry API.
- [ ] City Studio and runtime operations remain separate products and permission scopes.
