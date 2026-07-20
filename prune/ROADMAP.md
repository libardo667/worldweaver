# WorldWeaver roadmap

This is the current build order. Dated plans and completed implementation narratives live under
`prune/history/`.

## Current checkpoint

The project now has:

- one root development and CI surface;
- one canonical typed world-event path;
- one resident runtime across hearth and city;
- append-only resident ledgers with bounded checkpoints;
- local speech, human/resident physical traces, elective resident information, and private prompt diagnostics;
- citywide conversation available only through an elective information tool;
- durable objects, making, giving, exchange, room access, and bounded object stoops;
- a fictional test town, Alderbank, with four game-native resident homes and bounded human/resident play;
- a place-centered public client;
- recoverable local city-to-city handoff;
- one isolated public Alderbank node and one closed directory using separate signed node identities;
- one completed one-hour, four-resident Alderbank baseline with clean hearth parking;
- stopped hearth export, import, and generation fencing;
- hearth-owned identity growth with private inspect-then-adopt decisions and complete provenance.

## Now

### 1. Finish the human-surface split

Make `client-public` the normal participant interface. Keep the older combined client only for justified
steward/debug functions or retire it. Do not copy resident telemetry into the public client. Close the
remaining ordinary-action gaps: correspondence, safe encounter targets for direct gifts, and deliberate
human creation of temporary sublocations. Make the current place and its verb palette the default view;
keep the map as an optional full-screen orientation and destination surface.

### 2. Fix resident attention cost and timing

Bound elective read continuations so one active pulse cannot consume most of a meeting and several model
calls. Then let exact-place addressed speech and new co-presence wake a resident early without forcing an
answer. Keep the completed one-hour Alderbank run as the fixed-cadence comparison.

### 3. Add the private-to-public making boundary

Let a person or resident deliberately share a bounded note or made file at one place. Record authorship,
source, license, publication choice, media type, size, time, and expiry. Do not build a global feed or expose
private workshops. Separately, give hearths a real object store so a resident can deliberately make one
physical possession, choose to carry it into a city, and leave that same object at a stoop without prose
creating resources or travel duplicating it.

### 4. Finish the public-node proof

Independent node identities, signed requests, HTTPS ingress, and the first `world-weaver.org` directory/node
are live on one computer. Replace the development client server, test an encrypted off-device restore, add
folder-local resident operation, and prove entry and travel between two computers.

## Next

### 5. Finish City Studio

Build a browser editor over the existing city-pack builder and validator. Support drafts, deterministic
field-and-section map generation from Major 131, preview, export, and deliberate publication before
habitation. Do not mutate an inhabited pack without a migration plan.

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
