# Finish cross-node travel

## Status

The local end-to-end travel path now exists. City packs define stable travel hubs and routes. The source
node records and retries departure, the destination validates its own arrival hub and starts the same actor,
and the federation records `departing -> traveling -> arrived`. Residents can inspect available routes and
request travel. Occupancy queries deduplicate by actor identity.

The commons client now exposes the same local handoff to people. A route appears only at its actual local
gateway. Departure removes the source presence, redirects with only a random travel ID, and lets the
destination authenticate the actor and retry arrival. Browser session IDs and locations are separate for
each shard even when several local shards share one client origin.

Authentication no longer changes an actor's recorded city. Ordinary human entry checks the federation
attachment before creating local state and rejects a second local session. A person therefore cannot open
another city tab and silently bypass the travel lifecycle.

The old plan said a resident's private runtime payload had to move with every city trip. That is no longer
the design. A resident's hearth remains private and may keep running on its current host while the resident
attaches to a remote city. Moving the hearth itself is the separate host-migration problem in Major 127.

## Remaining problem

Travel has been proven between local Docker shards that share a federation secret. It has not yet been
proven between independently operated computers with separate node identities. The server handoff and
browser flow are actor-scoped and check the authenticated player. The remaining gap is trust and
reachability between independently operated computers, not the local human travel flow.

Node registration, pulses, route discovery, and source-side recovery records now carry an optional human
client URL separately from the shard API URL. Password-reset mail uses the same human URL when configured.
The commons client can serve local destinations honestly from one origin: `/ww-sfo`, `/ww-pdx`, and other
generated shard prefixes keep their API traffic on the matching same-origin proxy. Local node registration
advertises its prefix automatically; a deployed steward can override it with `WW_CLIENT_URL`.

Independent operation also needs a clear filesystem boundary. Each shard should run from its own folder.
That folder is the steward's unit of operation: it holds the node's configuration, private identity, city
data, local state, backups, and logs. It must not depend on a neighboring WorldWeaver source checkout or
share writable state or credentials with another shard. Shared, versioned container images are replaceable
software; the shard folder is the local node.

## Build next

1. Define and generate a self-contained shard folder with a stable node ID, a private signing key, a public
   descriptor, node-owned data, and safe backup boundaries.
2. Replace the shared federation token with per-node authentication and signed requests.
3. Bind each departure and arrival transition to the node authorized to make it.
4. Run the folder against published, versioned images so it does not reach into a neighboring source tree.
5. Give a steward one plain setup/check/start/stop/update/backup workflow that operates only on that folder
   and does not print or copy private credentials.
6. Put two independently created node folders behind real HTTPS addresses on different computers or trust
   domains.
7. Prove that a resident can remain hosted at their hearth, visit a remote city, and return without copying
   the complete hearth to that city.
8. Configure and verify a real public-client URL for each independently hosted destination.
9. Test directory outage, destination outage, interrupted departure, interrupted arrival, and replay across
   independently operated nodes.

## Rules

- `actor_id` identifies the person; `session_id` is only a local runtime handle.
- A city pack describes possible routes. A live node directory only reports which destinations are
  currently hosted and reachable.
- The source node retires the source session before confirming departure.
- The destination alone resolves its arrival hub and confirms arrival.
- A traveling actor must not appear active in two cities.
- Signing in proves identity; it never changes city attachment.
- The coordinator stores handoff state, not the resident's private hearth.
- Each city remains usable when its directory or peer is offline.
- A node's private key and local data stay inside its shard folder and never enter its public descriptor,
  city pack, logs, command output, or source control.
- Copying public configuration is not enough to impersonate a node; restoring private state requires an
  explicit backup and recovery path.

## Acceptance criteria

- [x] Humans and residents have durable actor IDs separate from local sessions.
- [x] Departure, traveling, arrival, and retry states are explicit and idempotent.
- [x] Destination arrival preserves the actor ID and uses a destination-owned hub.
- [x] Resident travel can be requested through an elective world capability.
- [x] Occupancy reads deduplicate current presence by actor identity.
- [ ] Independently operated nodes authenticate travel with separate identities.
- [ ] Two shards created in separate folders share no writable state, credentials, Docker project identity,
  or dependency on a neighboring source checkout.
- [ ] A steward can set up, inspect, start, stop, update, and back up one shard from its folder through a
  documented command surface.
- [ ] A two-computer HTTPS test completes city-to-city travel and return.
- [ ] No tested failure leaves one actor active in both cities.
- [x] The public client offers the same travel contract to a human.
- [ ] Directory failure leaves local life intact and reports remote travel as unavailable.
