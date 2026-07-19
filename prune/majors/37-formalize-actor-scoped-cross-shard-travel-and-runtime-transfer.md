# Finish cross-node travel

## Status

The local end-to-end travel path now exists. City packs define stable travel hubs and routes. The source
node records and retries departure, the destination validates its own arrival hub and starts the same actor,
and the federation records `departing -> traveling -> arrived`. Residents can inspect available routes and
request travel. Occupancy queries deduplicate by actor identity.

The old plan said a resident's private runtime payload had to move with every city trip. That is no longer
the design. A resident's hearth remains private and may keep running on its current host while the resident
attaches to a remote city. Moving the hearth itself is the separate host-migration problem in Major 127.

## Remaining problem

Travel has been proven between local Docker shards that share a federation secret. It has not yet been
proven between independently operated computers with separate node identities. The public client also does
not yet provide an ordinary human travel flow.

## Build next

1. Replace the shared federation token with per-node authentication and signed requests.
2. Bind each departure and arrival transition to the node authorized to make it.
3. Put two nodes behind real HTTPS addresses on different computers or trust domains.
4. Prove that a resident can remain hosted at their hearth, visit a remote city, and return without copying
   the complete hearth to that city.
5. Add a clear human travel control to the commons client using the same departure and arrival contracts.
6. Make failed, offline, and retryable travel states visible without reviving a ghost session.
7. Test directory outage, destination outage, interrupted departure, interrupted arrival, and replay.

## Rules

- `actor_id` identifies the person; `session_id` is only a local runtime handle.
- A city pack describes possible routes. A live node directory only reports which destinations are
  currently hosted and reachable.
- The source node retires the source session before confirming departure.
- The destination alone resolves its arrival hub and confirms arrival.
- A traveling actor must not appear active in two cities.
- The coordinator stores handoff state, not the resident's private hearth.
- Each city remains usable when its directory or peer is offline.

## Acceptance criteria

- [x] Humans and residents have durable actor IDs separate from local sessions.
- [x] Departure, traveling, arrival, and retry states are explicit and idempotent.
- [x] Destination arrival preserves the actor ID and uses a destination-owned hub.
- [x] Resident travel can be requested through an elective world capability.
- [x] Occupancy reads deduplicate current presence by actor identity.
- [ ] Independently operated nodes authenticate travel with separate identities.
- [ ] A two-computer HTTPS test completes city-to-city travel and return.
- [ ] No tested failure leaves one actor active in both cities.
- [ ] The public client offers the same travel contract to a human.
- [ ] Directory failure leaves local life intact and reports remote travel as unavailable.
