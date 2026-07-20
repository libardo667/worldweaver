# Build a private steward operations surface

## Status

The ordinary commons client is now deliberately free of shard-wide resident telemetry. Useful operating
signals still exist in the old combined client and backend, but they have not been reduced to a separate,
authenticated product with a written privacy boundary.

The old “semi-public observatory” and “player shadow” proposals are rejected. Read-only surveillance is
still surveillance, and a federation-held AI copy of a human is not part of the current resident model.

The 2026-07-19 CognitiveCore audit found a more urgent backend contradiction. The source repair landed on
2026-07-20: residents no longer copy their reduced private state into city session variables; the generic state
read/write, city-held growth, rest-metrics, cleanup, pruning, and whole-world reset routes are gone; development
reset and seeding default off; and a database migration removes old mirror fields from existing sessions. The
old combined client now shows only public roster presence rather than private rest and cognitive measurements.

That closes the worst disclosure and arbitrary-mutation path in source, but does not finish this work item.
Exact prompt capture now defaults off and requires `--trace-prompts` on a bounded resident or cohort run.
Expiry, purpose and access receipts, and a tested purge path remain open. Agent bootstrap, leave, messaging,
and travel still need a resident/host credential: checks that protect a human-owned session can accept an
anonymous request when the session belongs to a resident. The public Alderbank image also remains unsafe until
this repair is built, deployed, and checked against its live OpenAPI document. See
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

The resident credential must be narrower than either existing shortcut. Giving the resident process the
shard's JWT secret would let it impersonate every resident on that shard. Giving it the current node signing
key would make a temporary host the resident's permanent authority and would stop working cleanly after
cross-node travel. The capability must instead bind one `actor_id`, one active `runtime_generation`, an
allowlist of city operations, and a short validity window. It must be transferable or freshly issued during
travel, revocable without changing resident identity, and usable by a temporary host without making that host
the resident's owner.

The route and key audit found that this boundary covers more than bootstrap and travel. Movement, local
speech, marks, objects, making, stoops, exchanges, space access, and correspondence also accept a session ID
without proving caller control. Administrative doula, graph, seed, and reset routes require node/steward
authority or removal, not a broader resident token. The versioned signing and rollout contract is recorded in
[`resident-authority-route-and-key-boundary.md`](../../research/audits/cognitive-core/resident-authority-route-and-key-boundary.md).

## Never show or control

- prompt or response text;
- private ledger, memories, beliefs, letters, hearth files, or workshop contents;
- resident preference, reward, personality, growth, or behavior-target controls;
- shard-wide live prose feeds presented as operations data;
- a public roster with rest reasons, wake estimates, private goals, or runtime queues.

An emergency diagnostic that genuinely needs sensitive data must be a separate, time-bounded, audited
procedure rather than a permanent dashboard field.

## Acceptance criteria

- [x] A resident's private reduced state is not copied into a visited city's session storage.
- [x] Generic public state read/write, legacy city-growth, rest-metrics, cleanup, pruning, and reset routes do
  not exist; old mirrored fields are removed during database migration.
- [x] An ordinary resident run creates no exact prompt trace; bounded diagnostics require explicit opt-in.
- [x] New and started hearths enforce owner-only directories and private-file permissions without following
  links outside the hearth.
- [x] Elective-read receipts do not copy queries, returned prose, or ordinary source record IDs into durable
  resident history; identity growth retains only the proposal ID required for explicit adoption.
- [ ] Resident bootstrap, private/session-enriched reads, leave, messages, movement, typed world commands, and
  travel require actor-and-generation-scoped authority.
- [ ] Prompt diagnostics record their purpose and expiry, expose access receipts, and have a tested purge path.
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
