# Make resident hearths portable across temporary hosts

## Status

The local stopped-migration foundation is built:

- every initialized hearth has a versioned manifest with stable actor and hearth IDs;
- a fail-closed inventory separates portable resident data from host grants, credentials, caches, and city
  sessions;
- deterministic export and import verify file hashes and paths;
- runtime-generation fencing and a host-local lock stop a retired copy from waking normally;
- resident startup and clean shutdown enforce owner-only hearth directories and regular files without
  following links outside the hearth;
- the root preflight can inspect, activate, wake, and park one named resident safely;
- older `the-stable` homes can be imported through an explicit allowlist.

The work is not complete. Existing residents are not all initialized, archives are not encrypted or signed,
hearth-host authorization is not defined, and no cross-computer migration or remote-city attachment has been
proven. Active city nodes now have separate signing identities; that does not by itself authorize a computer
to run a resident's hearth.

## Model

- `actor_id` identifies the resident.
- `hearth_shard_id` identifies their private home shard.
- `current_world_shard` is the one hearth or city they are currently attached to.
- `runtime_host_id` is the temporary computer supplying service.
- `runtime_generation` fences orderly migration between cooperating hosts.

A host supplies compute and storage. It does not own the resident. Visiting another city does not move the
whole hearth; moving the hearth to another computer is a separate operation.

## Build next

1. Initialize manifests for current residents through reviewed, idempotent migration commands.
2. Add archive encryption and signatures without storing the only recovery key in a federation directory.
3. Define explicit hearth-host authorization using cryptographic identity without treating the host as the
   resident's owner.
4. Authorize a host and generation explicitly before it may wake a hearth.
5. Prove a stopped hearth transfer between two clean computers, including interruption at every write.
6. Prove that a resident hosted on one computer can attach over HTTPS to a city on another without giving
   that city the private hearth.
7. Design crash recovery separately. Do not claim that generation fencing revokes an undisclosed offline
   copy.

Host authorization and city action authority are related but not interchangeable. A shard-wide JWT secret
would let any holder impersonate every resident on that shard. A node signing key identifies the temporary
machine operating a node; it does not become the resident's identity. Any city capability issued to the
runtime must bind one actor and active generation, carry only the required operations and audience, expire,
and be replaceable during travel or host migration without transferring ownership to the host.

## Boundaries

- No canonical identity field names a permanent owner computer.
- Federation directories hold public routing and coordination projections, not the only private copy.
- City sessions, steward secrets, absolute paths, and host grants never enter a portable archive.
- Export fails while a resident is awake.
- Import never overwrites an existing home.
- Local hearth use survives directory and remote-city outages.
- Guardian or quorum recovery requires its own consent and threat model.

## Acceptance criteria

- [x] The architecture separates resident, hearth, current world, host, and runtime generation.
- [x] A manifest can be validated without starting cognition.
- [x] Export/import is deterministic, integrity-checked, and excludes machine-local state and secrets.
- [x] A newer stopped generation can activate while the retired source refuses normal startup.
- [x] Offline migration and interruption tests pass on synthetic homes.
- [x] New and started hearths enforce owner-only filesystem permissions on the temporary host.
- [ ] Existing resident homes have reviewed, valid manifests.
- [ ] Archives support encryption and authenticated origin.
- [ ] Independent hosts use separate identities and explicit authorization.
- [ ] A two-computer stopped migration preserves identity, full ledger evidence, and resident-owned artifacts.
- [ ] One host can run the hearth while the resident visits a remote city over HTTPS.
- [ ] Directory outage leaves the local hearth usable.
