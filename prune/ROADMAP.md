# WorldWeaver roadmap

This is the current build order. Dated plans and completed implementation narratives live under
`prune/history/`.

## Current checkpoint

The project now has:

- one root development and CI surface;
- one canonical typed world-event path;
- one resident runtime across hearth and city;
- append-only resident ledgers with bounded checkpoints;
- local speech, elective information, physical traces, and private prompt diagnostics;
- citywide conversation available only through an elective information tool;
- durable objects, making, giving, exchange, room access, and bounded object stoops;
- a fictional test town, Alderbank, with four game-native resident homes and bounded human/resident play;
- a place-centered public client;
- recoverable local city-to-city handoff;
- stopped hearth export, import, and generation fencing;
- hearth-owned identity growth with one-time migration from older city rows.

## Now

### 1. Finish resident-owned identity growth

Give residents a local, explicit way to consider and adopt their private self-edit proposals. Keep the
proposal, decision, and source event IDs in the hearth. Do not restore automatic city promotion, population
comparison, or text-pattern censorship.

### 2. Finish the human-surface split

Make `client-public` the normal participant interface. Keep the older combined client only for justified
steward/debug functions or retire it. Do not copy resident telemetry into the public client.

### 3. Add artifact stoops

Let a person or resident deliberately share a bounded note or made file at one place. Record authorship,
source, license, publication choice, media type, size, time, and expiry. Do not build a global feed or expose
private workshops.

### 4. Establish real node trust

Replace the shared federation token with independent node identities and signed requests. Bring up stable
HTTPS ingress, publish the first `world-weaver.org` directory/node, and prove travel between two computers.

## Next

### 5. Finish City Studio

Build a browser editor over the existing city-pack builder and validator. Support drafts, preview, export,
and deliberate publication before habitation. Do not mutate an inhabited pack without a migration plan.

### 6. Finish resident portability and recovery

Add host authorization, address rotation, recovery from an unavailable host, and independent-node tests.
Keep the rule that hosting supplies service rather than ownership.

### 7. Continue the private game-town lane

Use Alderbank to test understandable consequences over multiple sessions. Keep game rules opt-in and
constructive. Do not turn game telemetry into general resident assessment.

## Later

- local model distillation and cost reduction;
- source verification for explicitly epistemic roles;
- private correspondence refinements;
- durable spend and energy accounting;
- additional public cities and discovery models.

Experiments, publication tasks, and completed work are intentionally absent from this list. See
[`prune/README.md`](README.md) for those lanes.
