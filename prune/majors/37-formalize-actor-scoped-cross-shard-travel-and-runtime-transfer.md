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

The 2026-07-19 privacy and custody audit found that this guarantee does not extend to resident control. Agent
bootstrap accepts no resident/host credential. Leave and source-travel ownership checks reject the wrong human
player but accept an anonymous caller when `player_id` is empty, as it is for residents. Destination arrival
likewise treats an unauthenticated request as valid when the federation record says `agent`. Signed node calls
protect the federation coordinator after the city begins a handoff; they do not authenticate who told the city
to act for the resident. The existing anonymous resident travel tests codify this gap.

The old plan said a resident's private runtime payload had to move with every city trip. That is no longer
the design. A resident's hearth remains private and may keep running on its current host while the resident
attaches to a remote city. Moving the hearth itself is the separate host-migration problem in Major 127.

## Remaining problem

Travel has been proven between local Docker shards and later between separate signing identities. It has not
yet been proven between independently operated computers. The human browser flow is actor-scoped, but the
resident-facing city handoff has no actor/host capability. The remaining gaps are therefore both authority at
the resident edge and trust/reachability between independently operated computers.

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

New shard folders now generate their own Ed25519 signing key and safe-to-share public descriptor. Private
federation requests sign the method, path, exact body, timestamp, and a one-time nonce. The world root binds
a pre-admitted node ID to its registered public key, rejects later impersonation, prevents replay, and checks that
the signed caller is the node named by registration, pulses, travel transitions, mail, and account origin.
The active Alderbank, Portland, and San Francisco folders have been migrated, their keys are bound at the
local world root, and the shared token has been removed from those folders and the root. Live startup pulses
were accepted under all three identities while an unsigned private-directory request was rejected. The
stopped Portland deal/grow/keep variants were research runtimes, not future public nodes. They have been
moved out of `shards/` into the private artifact store, so their old shared registry ID can no longer collide
with live-node discovery.

On 2026-07-19, a throwaway agent actor made a live Portland-to-San-Francisco trip and returned through the
ordinary city session endpoints. Portland retired its local session before San Francisco created one at
Embarcadero; San Francisco then retired that session before Portland recreated one at Pearl District. Checks
at both ends found exactly one active local session. A Portland-signed request attempting to confirm the San
Francisco arrival was rejected with HTTP 403. Both travel records reached `arrived`, the actor finished active
in Portland, and all probe rows were removed afterward. This proves the local multi-node path and its separate
signing identities; it is not yet the required two-computer HTTPS proof.

The standalone generator now writes image-only Compose files and a folder-local operator. A clean temporary
folder ran without either source tree mounted, seeded its copied city pack, kept residents stopped, backed up
its database, secrets, identity, city data, and resident directory, restored them, and passed its safety
check. The next isolation proof is two independently created folders, then two computers.

That two-folder check now passes locally as well: disposable Portland and Alderbank nodes ran concurrently
with different project names, ports, credentials, keys, networks, and database volumes. Neither mounted the
monorepo or woke its agents. This still does not replace the two-computer HTTPS test.

The directory trust gap is now closed by default. A steward must admit a public `node.json` and record a
reason before a node can register. Revocation hides that node and blocks private federation calls. Key
replacement requires revocation first and a separately reviewed replacement descriptor. Every change leaves
an audit row. The migrated live directory retained its three known cities and rejected an uninvited signed
registration with HTTP 403.

A separate image-backed directory and Alderbank folder are now publicly reachable over HTTPS on one computer.
Their origin ports bind only to loopback, and the public directory lists the isolated Alderbank identity and
HTTPS address. This proves public reachability and separate node state, but it is not the required trip between
two computers. No resident was woken for this infrastructure check.

## Build next

1. Give the current resident runtime an actor-scoped city capability. Require it for bootstrap, leave,
   departure, retry, and arrival without turning the temporary host into the resident's owner.
2. Add wrong-resident, wrong-host, stale-generation, anonymous, and replay tests at the city edge as well as
   the signed federation edge.
3. Put two independently created node folders behind real HTTPS addresses on different computers or trust
   domains.
4. Prove that a resident can remain hosted at their hearth, visit a remote city, and return without copying
   the complete hearth to that city.
5. Configure and verify a real public-client URL for each independently hosted destination.
6. Test directory outage, destination outage, interrupted departure, interrupted arrival, and replay across
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
- [ ] Bootstrap, leave, and travel require an actor-scoped resident/host capability and reject anonymous or
  stale-generation callers.
- [ ] Independently operated nodes authenticate travel with separate identities.
- [x] Two shards created in separate folders share no writable state, credentials, Docker project identity,
  or dependency on a neighboring source checkout.
- [x] A steward can set up, inspect, start, stop, update, and back up one shard from its folder through a
  documented command surface.
- [ ] A two-computer HTTPS test completes city-to-city travel and return.
- [ ] No tested failure leaves one actor active in both cities.
- [x] The public client offers the same travel contract to a human.
- [ ] Directory failure leaves local life intact and reports remote travel as unavailable.
