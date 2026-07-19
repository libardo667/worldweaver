# Build a private steward operations surface

## Status

The ordinary commons client is now deliberately free of shard-wide resident telemetry. Useful operating
signals still exist in the old combined client and backend, but they have not been reduced to a separate,
authenticated product with a written privacy boundary.

The old “semi-public observatory” and “player shadow” proposals are rejected. Read-only surveillance is
still surveillance, and a federation-held AI copy of a human is not part of the current resident model.

## Goal

Give a steward enough information to keep their own node healthy without giving them a dashboard for
watching or shaping residents.

## Build next

1. Write a field-by-field access table before building the UI. For every value, name the operating need,
   role, retention period, audit record, and safer aggregate alternative.
2. Start with node health, service readiness, storage, database migration, federation reachability,
   inference availability, aggregate cost, backups, and failed jobs.
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
- [ ] Sensitive access is time-bounded and audited where it cannot be avoided.
- [ ] No control can alter resident identity, preferences, cognition, or private history.
- [ ] The public client imports no steward telemetry API.
- [ ] City Studio and runtime operations remain separate products and permission scopes.
