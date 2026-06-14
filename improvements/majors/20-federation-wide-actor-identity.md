# Federation-wide actor identity for humans and residents

## Problem

Identity is currently fragmented across shard-local tables and runtime-specific files.

- Human accounts are stored in each shard's local `players` table. A player who
  registers in one city does not automatically exist in another shard.
- Auth tokens currently encode the local `players.id`, not a federation-wide
  identity. That makes cross-shard login and travel brittle.
- AI residents are identified by a mix of resident directory names, session IDs,
  and `resident_id.txt` files. The federation tracks residents, but that record
  is not yet the canonical source of identity.
- `session_vars.player_id` links a session to a local player row, which means
  "who this person is" changes shape when they cross a shard boundary.
- Cross-shard travel, DMs, observatory timelines, player shadows, and future
  consent/identity rituals all need one durable identifier that survives shard
  changes, local DB resets, and runtime restarts.

Without a federation-wide identity layer, travel is really handoff between local
records rather than movement of one actor through one world.

## Proposed Solution

Introduce a canonical federation-wide `actor_id` and make it the identity spine
for all humans and AI residents.

### Phase 1 - Canonical actor model in `ww_world`

Add an authoritative `FederationActor` record in the federation root database.

Each actor gets:

- `actor_id` (UUID, permanent, never reused)
- `actor_type` (`human`, `agent`, `player_shadow`; leave room for `institution`)
- `display_name`
- `handle` or slug
- `home_shard`
- `current_shard`
- `status` (`active`, `dormant`, `traveling`, `missing`, `retired`)
- `origin` metadata (`registered`, `doula`, `shadow`, `migrated`)
- `created_at`, `updated_at`

This record becomes the canonical identity for:

- human accounts
- AI residents
- player shadows seeded by the doula

`FederationResident` then becomes either:

- a projection/materialized view of actor state for observability, or
- is folded into the new actor table if the duplication is not justified

### Phase 2 - Local shard projections point to `actor_id`

Keep shard-local tables for runtime and auth, but demote them to projections.

- Add `actor_id` to `players` with a unique constraint
- Add `actor_id` to `session_vars`
- Add `actor_id` to direct-message and travel records where identity continuity matters
- Treat local `players.id` as a shard-local implementation key only

JWTs should encode `actor_id` as the canonical subject. A shard should resolve
that token into a local player projection row, creating or updating it from the
federation record as needed.

### Phase 3 - Human registration and login become federation-aware

When a human registers on any city shard:

1. The shard requests a new `actor_id` from `ww_world`
2. `ww_world` creates the canonical actor record
3. The local shard creates its `players` row with the returned `actor_id`
4. The JWT subject is the `actor_id`, not the local player row ID

When a human logs into a different shard:

1. The token resolves to `actor_id`
2. The shard looks up that `actor_id` in its local `players` projection
3. If absent, it hydrates a local projection from `ww_world`
4. Session bootstrap binds the session to `actor_id`

This makes one human account portable across the federation without duplicating
their identity.

### Phase 4 - AI residents use the same identity spine

For agents:

- `resident_id.txt` becomes the actor's federation-wide `actor_id`
- Doula spawn mints a new actor first, then scaffolds the resident directory
- `../ww_agent` bootstraps sessions and federation pulses using `actor_id`
- Cross-shard DMs and travel use `actor_id` as the sender/recipient identity

For player shadows:

- the shadow gets its own `actor_id`
- it stores a link back to the originating human actor (`source_actor_id`)
- the relationship is explicit in federation metadata rather than inferred from names

### Phase 5 - Travel and handoff semantics

Cross-shard travel should move one actor, not recreate them.

For human travel:

- origin shard records departure for `actor_id`
- destination shard resolves or creates the local player projection for `actor_id`
- destination session binds to the same `actor_id`
- inbox/history/observatory surfaces continue under the same identity

For agent travel:

- the existing traveling state and pulse flow use `actor_id` as the durable identity
- arrival updates `current_shard` on the actor record
- the receiving shard can bootstrap the same actor without identity drift

### Phase 6 - Migration of existing humans and residents

Backfill current data:

- each existing local player gets a new `actor_id` and federation actor row
- each existing resident directory gets an `actor_id` written to `resident_id.txt`
- existing federation resident rows are mapped onto actor rows
- existing sessions gain `session_vars.actor_id`

Migration must be idempotent so partially migrated shards can be retried safely.

## Files Affected

- `src/models/__init__.py` - add `FederationActor`; add `actor_id` fields to local models
- `alembic/versions/<hash>_add_federation_actor_identity.py` - schema migration
- `src/api/auth/routes.py` - register/login/me become actor-aware
- `src/services/auth_service.py` - JWT subject changes from local player ID to `actor_id`
- `src/api/federation/routes.py` - actor registration, lookup, sync, and travel endpoints
- `src/api/game/state.py` - session bootstrap binds sessions to `actor_id`
- `src/services/federation_pulse.py` - pulse payloads use `actor_id`
- `src/models/schemas.py` - add request/response models for actor sync endpoints
- `src/services/session_service.py` - local session identity helpers resolve via `actor_id`
- `src/api/game/settings_api.py` - per-player settings lookups follow `actor_id`
- `tests/api/test_auth_routes.py` - cross-shard auth and hydration tests
- `tests/api/test_federation_routes.py` - actor registration and sync tests
- `tests/integration/test_cross_shard_actor_identity.py` - end-to-end travel/auth continuity
- `../ww_agent/src/identity/loader.py` - resident identity loads and persists `actor_id`
- `../ww_agent/src/resident.py` - bootstrap/session logic uses `actor_id`
- `../ww_agent/src/services` or federation client modules - resolve and pulse by `actor_id`
- `../ww_agent/residents/*/identity/resident_id.txt` - migrated to canonical actor IDs

## Acceptance Criteria

- [ ] A human who registers on one shard receives a federation-wide `actor_id`
- [ ] The JWT subject is `actor_id`, not the shard-local `players.id`
- [ ] Logging into a second shard rehydrates the same human identity instead of creating a second account
- [ ] `session_vars` binds sessions to `actor_id`
- [ ] Newly spawned AI residents receive an `actor_id` before first boot
- [ ] `resident_id.txt` and federation resident tracking refer to the same durable ID
- [ ] Cross-shard travel preserves one continuous identity for both humans and agents
- [ ] Cross-shard DMs are addressed by `actor_id`, not local shard-specific IDs
- [ ] Existing human accounts and existing residents migrate without identity collisions
- [ ] Observatory/federation views can show one actor's history across shards under a single identifier

## Risks & Rollback

- This touches auth, travel, federation, session bootstrap, and agent runtime at once.
  Roll it out behind a feature flag or staged migration path rather than flipping all
  shards at once.
- Changing JWT subject semantics is breaking. During migration, support decoding both
  legacy local player IDs and new `actor_id` subjects until all shards are upgraded.
- If federation root is unavailable during registration or shard hydration, account
  creation and cross-shard login need a clear failure mode. Do not silently mint
  shard-local fallback identities that later collide.
- Existing residents may have ad hoc or duplicate `resident_id.txt` values. Migration
  must detect collisions and stop for manual repair rather than inventing ambiguous links.
- Rollback path: keep `actor_id` columns nullable at first, preserve legacy player-ID
  auth decoding during rollout, and avoid deleting old local identity fields until the
  federation-wide path has been validated end to end.
