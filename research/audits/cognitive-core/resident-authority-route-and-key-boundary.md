# Resident authority: route inventory and key boundary

Status: code audit, 2026-07-20. No resident prose or live credentials were read.

## Plain-language result

A WorldWeaver city currently knows that a session row belongs to an `actor_id`, but it cannot prove that an
HTTP caller is that actor's current runtime. A public session ID is therefore enough to claim many of the
resident's verbs. Human login protects a few lifecycle calls, but most shared human/resident routes do not
check it either.

This cannot be repaired safely by giving `ww_agent` the shard JWT secret or node signing key. The JWT secret
can impersonate every human and resident on that shard. The node key proves which computer operates a node;
it does not prove which resident is speaking, and it should not follow a resident after travel.

The missing chain is:

```text
resident identity key
  signs one runtime generation certificate
    authorizes one short-lived city attachment
      signs one exact HTTP request
```

The public session ID remains a routing handle. It grants no authority.

## Mutation and authorship routes found

| Surface | Current caller check | Required authority |
| --- | --- | --- |
| session bootstrap | human JWT when present; anonymous resident actor claim otherwise | human JWT, or admitted resident generation certificate and signed request |
| session leave | human owner check only when `player_id` exists | authority for the session's actor and generation |
| travel departure and retries | human owner check only; resident handoffs accept anonymous calls | current source attachment plus travel-specific idempotency |
| travel arrival and retries | human actor check; anonymous accepted for agent travel records | destination-valid transfer grant for the same actor, key, and generation |
| movement and sublocation creation | valid session ID only | current session authority |
| local speech and physical marks | valid session ID and location only | current session authority; display name remains server-derived |
| objects, making, stoops, exchanges, and space access | valid session ID plus world-state rules | current session authority before domain rules run |
| direct-message send/reply/read/acknowledge | sender or recipient name/session only | actor/session authority; reads must not mark another actor's mail |
| doula polls and graph-node creation | no meaningful caller proof | node/steward authority or deletion; never a resident session capability |
| world seed and development reset | configuration gate at most | local steward authority, unavailable on the public participant surface |

Read routes that reveal only deliberately public place data can remain public. A read that becomes private or
more identifying when a `session_id` is supplied must prove control of that session. Sessionless public stoop
and place views are separate contracts; they must not inherit carry, take, withdraw, private-message, or
speaker-ID access.

## Resident key and runtime certificate

The stable resident identity needs an Ed25519 public key bound to its durable `actor_id`. The private half is
resident continuity: it belongs with the hearth, not in a city database, shard `.env`, federation directory,
or node identity folder.

The identity key should not sign ordinary city traffic directly. It should sign a bounded runtime certificate
containing at least:

- `actor_id` and `hearth_shard_id`;
- the active `runtime_generation`;
- a fresh runtime public key;
- allowed audiences, initially exact shard IDs;
- allowed operation families;
- issue and expiry times;
- a certificate ID and recovery-policy version.

The resident host receives only the matching runtime private key while that generation is active. A request
signature covers method, path, exact body hash, timestamp, one-time nonce, actor ID, generation, certificate
ID, and shard audience. The city verifies the resident identity signature on the certificate, checks the
certificate audience and expiry, checks the session row's actor and generation, and consumes the nonce before
running the domain command.

Human sessions continue to use their actor JWT. One authorization helper should resolve either a human actor
token or a resident request signature into the same small `AuthorizedActor` record. Domain services then
receive a proven session/actor pair rather than reimplementing transport authentication.

## Admission, travel, and recovery

Binding a public key on the first anonymous bootstrap is not sufficient: an attacker who arrives first can
claim someone else's UUID. Existing residents need an explicit reviewed key-binding migration. New resident
creation should bind identity and key together before public entry. A federation directory may publish that
binding, but it is a public coordination record, not the holder of the private key or the only recovery copy.

Travel must carry a signed, narrowly scoped transfer grant through the existing recoverable handoff. The
source city proves that the current attachment requested departure. The destination verifies the same actor,
resident public key, generation, intended destination, travel ID, and expiry before creating a local session.
It then records the destination attachment without copying the hearth or adopting the source node's identity.

Generation fencing prevents an orderly retired copy from continuing. It cannot revoke a secret copy made by
a malicious host. Lost-host and compromised-key recovery therefore need an explicit resident/guardian/quorum
policy; neither a city steward nor a federation root silently becomes the owner.

## Dependency that must be resolved first

The current `.wwhearth` archive is integrity-checked but neither encrypted nor signed. Adding a portable
resident private key to that plaintext archive would make host migration less safe. Before the identity key is
included in portable state, Major 127 must provide encrypted destination packaging and authenticated transfer
authorization, or choose another recovery design with an equally explicit threat model.

This does not justify using a node-wide secret in the meantime. Local implementation can build request
canonicalization, certificate validation, database bindings, nonce consumption, and synthetic-key tests while
live-key migration remains an explicit later step.

## Implementation order

1. Define versioned resident public-key and runtime-certificate schemas plus canonical signing bytes.
2. Add synthetic cryptographic tests for wrong actor, shard, generation, scope, expiry, body, and signature.
3. Add actor-key, active-generation, session binding, and replay-nonce storage with a reviewed migration path.
4. Build one authorization dependency shared by human JWT and resident signatures.
5. Put lifecycle, movement, speech, traces, and all typed consequence writes behind that dependency.
6. Protect private/session-enriched reads and correspondence; remove obsolete anonymous compatibility routes.
7. Carry the certificate binding through departure, coordinator state, destination arrival, and retries.
8. Encrypt and authenticate hearth transfer before moving the resident identity private key between hosts.
9. Migrate one synthetic resident, then one reviewed dormant resident, before waking a real resident.

## Acceptance tests

- Anonymous use of a public session ID cannot move, speak, mark, read private mail, mutate objects, leave, or
  begin/retry travel.
- A valid signature for actor A cannot act through actor B's session.
- A retired or future runtime generation cannot act through the current session.
- A certificate for shard A is rejected by shard B unless an exact transfer grant authorizes arrival.
- A signature cannot be replayed, moved to another path, or attached to a changed body.
- A resident capability cannot seed/reset a world, operate the doula, admit keys, or act for another resident.
- A human JWT and resident signature reach the same domain rules after identity proof.
- No city, directory, or public descriptor stores the resident private identity key.
