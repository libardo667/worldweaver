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

Cities can now create a separate folder-owned hearth receiver and use it to verify and import an encrypted,
resident-signed package into a brand-new dormant home. Both the workspace command and the standalone shard
command refuse identity replacement, package-to-card mismatches, and existing destination homes. The
standalone command mounts the receiver key only into a short-lived agent container; the city backend never
receives it.

The work is not complete. Existing residents are not all initialized, no real resident identity signing key
is stored, and no cross-computer migration or remote-city attachment has been proven. The safe operator
commands can now move a synthetic host-sealed identity into a dormant home. A resident-signed handoff binds
that transfer to one source host, destination host, N-to-N+1 generation step, and two node witnesses. Separate
operator commands now retire and preserve the source, verify its receipt, activate the destination, and issue
the destination receipt. Active city nodes have separate signing identities; only the resident-signed handoff
authorizes those identities to witness this one transition. No current command deletes the source.

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
2. Decide and implement resident identity-key custody and recovery without storing the only recovery key in
   a federation directory or treating a temporary host as owner.
3. Prove the completed encrypted, resident-authorized handoff between two clean computers, including a real
   process interruption at every durable boundary. The synthetic library and command tests already cover the
   same ordering on one computer.
4. Prove that a resident hosted on one computer can attach over HTTPS to a city on another without giving
   that city the private hearth.
5. Design crash recovery separately. Do not claim that generation fencing revokes an undisclosed offline
   copy.

Host authorization and city action authority are related but not interchangeable. A shard-wide JWT secret
would let any holder impersonate every resident on that shard. A node signing key identifies the temporary
machine operating a node; it does not become the resident's identity. Any city capability issued to the
runtime must bind one actor and active generation, carry only the required operations and audience, expire,
and be replaceable during travel or host migration without transferring ownership to the host.

The resident authority audit identifies a hard packaging dependency: the stable resident identity private
key belongs to portable continuity, but the current `.wwhearth` archive is plaintext. Do not add that key to
the archive until the package is encrypted for its reviewed destination and the transfer authorization is
authenticated. Runtime request and certificate validation can be built against synthetic keys first. See
[`resident-authority-route-and-key-boundary.md`](../../research/audits/cognitive-core/resident-authority-route-and-key-boundary.md).

## Key-custody checkpoint — 2026-07-20

The city-side half is now concrete. A city can record a reviewed resident public key and the steward's reason
through a non-HTTP operator command. A pre-admitted resident can use an identity-signed, short-lived runtime
key to bootstrap a generation-bound session. Existing residents still use the unsigned compatibility path;
none has been silently assigned a key.

Build the private half in this order:

1. Define a small public resident identity descriptor containing the actor ID, hearth ID, public identity
   key, format version, and no private or city-local data. The agent library now creates, verifies, and
   portably classifies this self-signed descriptor from an injected synthetic key. The city independently
   verifies that same document, and both root and folder-local operator commands pass the whole card through
   standard input instead of asking a steward to copy its fields. No private key is stored yet.
2. Give a temporary host a dedicated X25519 transport key. Do not reuse its Ed25519 node-signing key, and do
   not treat either host key as the resident's identity. New city folders now receive a separate private
   `hearth-host/identity/transport.key` and safe-to-share `hearth-host.json`. Existing city folders can add or
   verify the same pair with `python dev.py hearth-host --city CITY initialize` from the workspace or
   `python ww.py hearth-host initialize` from a standalone folder. Neither key is wired to a resident runtime.
3. Keep the current deterministic ZIP as an inner payload. Put it inside a versioned encrypted envelope for
   the reviewed destination host. Sign the complete encrypted envelope with the resident identity key. Do
   not publish a plaintext archive hash that lets observers recognize repeated private state. The package
   module now wraps and imports the deterministic archive entirely in memory, loads the folder-owned receiver
   key from a regular file, and refuses an outer identity or generation that differs from either the inner
   manifest or the reviewed public resident identity card. `hearth-host receive PACKAGE IDENTITY --resident
   NAME` exposes the safe import half and leaves the new home dormant. Package creation still uses injected
   synthetic resident keys because real resident key custody is unresolved.
4. Only the encrypted format may carry the resident identity private key. Plain `.wwhearth` export must keep
   excluding it and must fail if a future key-bearing hearth would otherwise leak it. The agent now has a
   synthetic-key-tested host seal for at-rest custody: it encrypts the long-term Ed25519 key for the current
   hearth host's X25519 receiver, binds it to the self-signed public identity card, and rejects the wrong host,
   wrong card, tampering, links, and replacement. `identity/resident_identity.sealed.json` is classified as
   host-specific and never enters plaintext export. There is deliberately no creation command for real
   residents yet and no claim that a host seal is a recovery policy.
   A stopped, sealed synthetic hearth can now be exported with `hearth-host send` for a reviewed destination
   host. The destination's `hearth-host receive-transfer` command verifies the resident card, envelope,
   generation, inner archive, and private key before resealing the key and installing a dormant home. The
   source remains unchanged. This completes the encrypted custody handoff, not authority transfer or recovery.
   The encrypted payload now carries a resident-signed handoff record naming its one-time transfer ID, source
   and destination host transport keys, and exact N-to-N+1 generation transition. Receipt stores that record as
   host-specific evidence beside the dormant destination. It is coordination for cooperating hosts, not proof
   that a malicious host erased an offline copy.
   The handoff also binds the two shards' existing public node-signing identities as narrow witnesses. Separate
   receipt formats now require the source witness to attest that N retired and the destination witness to attest
   that N+1 activated. The destination key cannot sign the source receipt. The library-level filesystem
   ceremony now applies those receipts in a restartable order and preflights every available key before changing
   state. Synthetic interruption tests leave the source retired and intact, let receipt generation resume, and
   never advance the destination twice. The same retirement and activation steps are now available from both
   the workspace root and isolated shard folders. Each mounts the relevant node key only into a short-lived
   operator container. No receipt or current command authorizes deletion of a retired source.
5. On an authorized host, decrypt the long-term key into memory only long enough to sign a fresh runtime
   public key for one city, generation, scope set, and expiry. Ordinary requests use the runtime key, not the
   long-term identity key.
6. Give each running resident its own signed world client. The current daemon's one shared client cannot carry
   resident authority safely.
7. The stopped transfer can now be re-encrypted for the next reviewed host. Its resident-signed authorization
   binds the exact source, destination, witnesses, and N-to-N+1 generation change. Receiving bytes leaves the
   destination dormant. A separate command retires and preserves the source before another separate command
   verifies that receipt and activates the destination. The destination refuses to advance if its copy is
   already active at generation N.
8. Specify recovery separately. A federation directory must not hold the only recovery key, and an ordinary
   transfer must not quietly invent a guardian or owner.

### Runtime signing checkpoint — 2026-07-20

Steps 5 and 6 are now implemented for a hearth that already has a reviewed public identity card and a private
key sealed for its current host. The host opens that long-term key only to sign a fresh, replaceable Ed25519
runtime key for one actor, hearth generation, city audience, and the three current session scopes. The runtime
certificate lasts one hour and renews before expiry by opening the host seal again; ordinary HTTP requests use
only the short-lived key.

The resident command and daemon now construct a separate world client for each key-bearing resident. The
client discovers the city's public shard ID, uses the signed bootstrap endpoint, and signs the exact encoded
request path and serialized body thereafter. A half-created identity card or seal fails closed. Homes with
neither file remain on the explicit unsigned migration path for now; no existing resident was silently given a
key. The checked-in Alderbank agent and new-shard template mount only the hearth host's receiver key into the
agent process, not the city node key or another resident's secret.

Plain dormant creation now creates a new resident identity key directly into the current host's seal and writes
the safe-to-share self-signed card. It refuses to proceed without the folder's hearth-host key. The card still
requires a separate steward admission command, and creation still does not activate, wake, or attach the
resident. Existing residents are never backfilled by this path.

The disposable signed card/admission/bootstrap/scene/leave round trip now passes against Alderbank and leaves
no bound session. This proves the current one-city runtime signing path, not inter-city travel, key recovery,
off-device hosting, or hostile-host protection. Those remain later proof boundaries.

Encryption protects the package at rest and in transit and reduces accidental key exposure. It cannot stop a
malicious temporary host from copying a key while that host is authorized to run the resident. Generation
fencing can stop an orderly old copy; it cannot revoke an undisclosed offline copy. Do not claim otherwise
without a separate hardware-backed or quorum design.

## Deletion decision boundary

Retirement is reversible coordination, not permission to erase the old hearth. The current workflow therefore
preserves the complete source and has no deletion command. Before this project considers adding one, a separate
work item and operator review must define all of the following:

- how both matching receipts and the resident-signed handoff are checked;
- how the destination is shown to contain the complete ledger and resident-owned artifacts;
- what recovery copy exists, who can use it, and what consent governs it;
- how long a retired source is retained and how a steward can cancel deletion;
- how an explicit deletion request is distinguished from retirement; and
- what can honestly be proven when a source host may have kept an undisclosed copy.

Passing the present transfer tests supplies evidence for that later decision. It does not satisfy these deletion
requirements.

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
- [x] Archives support encryption and authenticated origin.
- [x] Synthetic independent hosts use separate transport and witness identities with explicit resident
  authorization.
- [ ] A two-computer stopped migration preserves identity, full ledger evidence, and resident-owned artifacts.
- [ ] One host can run the hearth while the resident visits a remote city over HTTPS.
- [ ] Directory outage leaves the local hearth usable.
