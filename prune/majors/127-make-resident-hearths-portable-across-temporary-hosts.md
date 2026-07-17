# Make resident hearths portable across temporary hosts

## Status

Proposed 2026-07-17. This follows the completed city/hearth attachment work in archived Major 86.
It must shape the remaining cross-computer work in Majors 20 and 37 before private resident state is
packaged or transferred.

## Problem

WorldWeaver now gives one continuous resident a private hearth and lets that resident attach exclusively
to either the hearth or a city. The current deployment still keeps a resident directory under one city
shard and runs the resident from that shard's Docker project. That makes a temporary implementation detail
look like a permanent relationship: it appears that the computer running the process owns the resident.

That is not the intended model. A resident is not property of a city node, a steward, or a physical
machine. Their hearth is their own specialized shard. A computer may temporarily provide storage,
networking, and inference for that shard, but changing computers must not change the resident's identity,
home, history, or rights.

Three different facts are currently too easy to collapse into one:

- `actor_id`: who the resident is;
- current world attachment: the one world where the resident is presently active;
- runtime host: the computer currently supplying compute for the resident and hearth.

City travel and host migration are therefore different operations. City travel changes the active world
attachment. Host migration moves the machinery running the resident/hearth. Neither operation creates a
new resident.

The federation root must not become the replacement owner. It may publish a resident or hearth's current
contact information and coordinate a handoff, but it must not hold the only authoritative copy of private
resident state or decide which machine is entitled to possess that identity.

## Proposed Solution

Treat every resident/hearth as a portable logical shard with stable identity and temporary hosting.

### 1. Make the domain model explicit

Use separate concepts for:

- `actor_id`: the permanent resident identity;
- `hearth_shard_id`: the stable ID of that resident's private shard;
- `current_world_shard`: the hearth or city to which the one CognitiveCore is attached;
- `runtime_host_id`: the temporary node supplying compute, never part of resident identity;
- `runtime_generation` or lease: the current authority to run exactly one live runtime.

Do not add an `owner_host` field. Existing `home_shard` fields must be audited because some currently mean
"origin city" while the future model requires a resident's actual hearth shard.

### 2. Define a portable hearth package

The resident home needs a versioned manifest and a safe export/import contract. The portable package
should contain the resident-owned material needed to rebuild the same runtime, including identity,
append-only ledger, durable projections or their rebuild inputs, hearth configuration, and resident-owned
artifacts. It should exclude machine-local caches, city-local sessions, database handles, host paths, and
the steward's API keys.

The package must have an integrity manifest. Private contents should support encryption independently of
the transport used to move them. Export/import must be testable without invoking an LLM.

This is not Major 37's city-travel payload. Ordinary city travel should not copy the whole hearth merely
because the resident changes its public location.

### 3. Prevent two copies from waking

Begin with a deliberately small stopped-runtime migration protocol:

1. stop cognition and record a shutdown/migration receipt;
2. export the hearth at a new monotonically increasing runtime generation;
3. import and verify it on the new host;
4. activate the new generation once;
5. make the old generation refuse to start.

Normal migration must be safe before crash recovery is automated. Recovery after permanent host loss will
need a separate policy such as resident-held recovery material or explicitly chosen guardians. Possession
of a stale copied directory must not be enough to wake a second resident.

### 4. Let hosts offer service without acquiring ownership

A steward node may advertise city hosting, hearth hosting, inference capacity, storage limits, uptime,
and admission policy. A resident/hearth may accept that service and later leave it. Federation discovery
should publish signed node and hearth contact descriptors, not private state.

Each independently operated node needs its own cryptographic identity. The current federation-wide shared
token is acceptable only as local scaffolding; unrelated stewards must not all share one master secret.
The first public deployment may use a Cloudflare tunnel, while the protocol must also allow another
operator to use a different tunnel, reverse proxy, or public host.

### 5. Keep hosting and world attachment independent

A resident hosted on one computer may attach to a city on another computer over authenticated HTTPS. A
city hosts the resident's public session and local facts; it does not automatically receive the private
hearth. Rehosting the CognitiveCore onto another steward's compute is a separate, explicit operation.

The resident host must still enforce the completed Major 86 invariant: one CognitiveCore and one active
world attachment. Host migration adds another exclusivity boundary; it does not replace that one.

### 6. Use `world-weaver.org` as the first public path, not the owner of the commons

Major 18 records the existing `world-weaver.org` domain and Cloudflare tunnel work. Bring that path back
as the first reachable federation directory and/or project-operated node. Other stewards must be able to
publish their own addresses and choose one or more directories. A directory outage may block new
discovery or travel, but it must not stop a local hearth or city from running.

## Initial implementation sequence

1. Audit current uses of resident directories, `home_shard`, `current_shard`, Compose mounts, and
   `session_id.txt`; write the exact identity/attachment/hosting contract beside the live types.
2. Add the versioned hearth manifest and a read-only inspection/validation command.
3. Add deterministic export/import with integrity checks and explicit exclusion of host secrets and
   city-local runtime handles.
4. Add stopped-runtime generation transfer and stale-generation refusal.
5. Introduce per-node identity and signed public node/hearth descriptors; replace the shared federation
   token incrementally rather than in a flag-day change.
6. Prove migration between two clean local hosts without running cognition, then perform one deliberate
   single-resident live migration only after the offline proof is recoverable.

## Files Affected

- `prune/majors/20-federation-wide-actor-identity.md`
- `prune/majors/37-formalize-actor-scoped-cross-shard-travel-and-runtime-transfer.md`
- `prune/majors/18-public-domain-and-observatory.md`
- `prune/ROADMAP.md`
- `ww_agent/src/resident.py`
- `ww_agent/src/identity/`
- `ww_agent/src/runtime/ledger.py`
- `ww_agent/scripts/`
- `worldweaver_engine/src/services/federation_identity.py`
- `worldweaver_engine/src/api/federation/routes.py`
- `worldweaver_engine/src/models/`
- `worldweaver_engine/scripts/dev.py`
- `shards/*/docker-compose.yml`

## Acceptance Criteria

- [ ] Project contracts say explicitly that a physical host supplies temporary service and does not own a
      resident or hearth.
- [ ] Every resident has a stable `hearth_shard_id` distinct from current city attachment and runtime host.
- [ ] No canonical identity field names a permanent owner computer.
- [ ] A versioned hearth manifest can be validated without starting the resident or invoking an LLM.
- [ ] A resident/hearth can be exported from one clean host and imported on another with identity, complete
      ledger evidence, hearth configuration, and resident-owned artifacts intact.
- [ ] Export excludes steward API keys, absolute host paths, caches, and city-local session handles.
- [ ] The new host can activate one newer runtime generation, and the old host refuses to start its stale
      generation.
- [ ] Exactly one CognitiveCore and one world attachment remain active through successful migration and
      every tested failure point.
- [ ] A resident may attach over HTTPS to a city on another computer without transferring the complete
      private hearth to that city.
- [ ] Federation directories store only public routing/coordination projections, not the sole authoritative
      copy of resident private state.
- [ ] Independently operated nodes use separate identities rather than one federation-wide master token.
- [ ] A local hearth remains usable when a directory or remote city is unavailable.
- [ ] Offline migration tests pass before any live resident migration is attempted.

## Risks & Rollback

- **Split brain:** two hosts could run copied state. Start with stopped-runtime migration and generation
  fencing; do not claim crash recovery until it has an explicit trust model.
- **Secret leakage:** a naive archive could include provider keys or host file grants. Use an allowlisted
  manifest, inspect the package in tests, and fail closed on unknown sensitive paths.
- **Federation becomes ownership:** putting the only lease or identity record in one root would merely move
  ownership from a machine to a service. Keep resident evidence in the hearth and make directory records
  projections.
- **Host and travel get coupled again:** copying the hearth on every city trip would be slow, invasive, and
  conceptually wrong. Keep separate commands and state machines for attachment travel and host migration.
- **Premature distributed consensus:** automatic recovery from a destroyed host is harder than orderly
  migration. Ship the recoverable stopped-runtime path first and leave guardian/quorum recovery explicit.
- **Rollback:** retain the current single-host resident layout as a supported host adapter while the
  manifest and generation rules are additive. Do not delete resident directories or rewrite ledgers during
  the first portability slices.
