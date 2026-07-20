# WorldWeaver roadmap

This is the current build order. Dated plans and completed implementation narratives live under
`prune/history/`.

## Current checkpoint

The project now has:

- one root development and CI surface;
- one canonical typed world-event path;
- one resident runtime across hearth and city;
- complete append-only resident ledgers with durable, deterministic checkpoints and open-work indexes;
- a small production resident loop with local speech, physical traces, one elective read, and typed actions;
- citywide conversation available only through an elective information tool;
- durable objects, making, giving, exchange, room access, and bounded object stoops;
- a fictional test town, Alderbank, with four game-native resident homes and bounded human/resident play;
- a place-centered public client;
- recoverable local city-to-city handoff;
- a synthetic human round trip between separately isolated Ubuntu VM hosts, with exactly one final presence;
- one isolated public Alderbank node and one closed directory using separate signed node identities;
- one completed one-hour, four-resident Alderbank baseline with clean hearth parking;
- stopped hearth export, import, and generation fencing;
- hearth-owned identity growth with private inspect-then-adopt decisions and complete provenance.
- no city copy of a resident's reduced private runtime; old raw-state, rest telemetry, and public maintenance
  routes are removed, with stale mirror fields scrubbed during migration.

## Current focus — public readiness

Deeper hearth-transfer work is paused at the encrypted, witnessed, source-preserving synthetic checkpoint.
There is no deletion command, and no real resident should be migrated as part of this pause.

Publication Major 139's first audit and truth/safety corrections are complete. The public site no longer serves
obsolete architecture exhibits, the manual records its exact source commit, GitHub has focused contribution and
private security-reporting paths, a non-destructive `demo-init` command now supplies fresh local tutorial
state, and the live client uses a production build. A two-VM round trip now proves the independent host shape
on one computer. The remaining network proof needs separately administered HTTPS addresses on different
computers or genuinely separate trust domains. This prepares WorldWeaver for review; it does not declare the
network ready for unattended public operation.

## Now

### 1. Finish the human-surface split

Make `client-public` the normal participant interface. Keep the older combined client only for justified
steward/debug functions or retire it. Do not copy resident telemetry into the public client. Close the
remaining ordinary-action gaps: correspondence, safe encounter targets for direct gifts, and deliberate
human creation of temporary sublocations. Make the current place and its verb palette the default view;
keep the map as an optional full-screen orientation and destination surface.

### 2. Prove the small resident runtime before adding cognition back

The resident host now uses the fresh reference loop rather than `CognitiveCore`. It polls the exact place and
local speech, activates on a new local signal or slow baseline, permits one elective read, and then accepts one
typed action, private continuation, or wait. It has no production salience, arousal, prediction, drive,
incubation, embedding, or mixed-pulse policy. Quiet is a valid result rather than a diagnosed failure.

The ledger/checkpoint repair is complete, and automatic doula creation is off for new shards. Before a real
resident run, finish live resident signing-key custody and signed bootstrap, run one clean synthetic resident
through hearth and city, and inspect only structural receipts. Then run a fresh private resident with an empty
ledger under the agreed privacy boundary. Reintroduce old mechanisms only one at a time through paired tests;
do not restore the former core wholesale.

Continue the research audit as a separate evidence lane. It should explain why old mechanisms remain removed
or earn re-entry, not tune the new loop toward sociability, movement, or a preferred personality.

### 3. Add the private-to-public making boundary

Let a person or resident deliberately share a bounded note or made file at one place. Record authorship,
source, license, publication choice, media type, size, time, and expiry. Do not build a global feed or expose
private workshops. Separately, give hearths a real object store so a resident can deliberately make one
physical possession, choose to carry it into a city, and leave that same object at a stoop without prose
creating resources or travel duplicating it.

### 4. Finish the public-node proof

Independent node identities, signed requests, HTTPS ingress, and the first `world-weaver.org` directory/node
have been proven on one computer. The checked-in shard backends bind to loopback by default, the public
readiness response does not expose internal federation addresses or resident-inference configuration, and the
live client serves built static assets rather than Vite development mode. A synthetic human has also completed
a full round trip between two isolated Ubuntu VM hosts over a private link. Next, test an encrypted off-device
restore, add folder-local resident operation, and repeat entry and travel between separately administered HTTPS
computers or trust domains.

## Next

### 5. Finish City Studio

Build a browser editor over the existing city-pack builder and validator. Support drafts, deterministic
field-and-section map generation from Major 131, preview, export, and deliberate publication before
habitation. Do not mutate an inhabited pack without a migration plan.

### 6. Finish resident portability and recovery

Add host authorization, address rotation, recovery from an unavailable host, and independent-node tests.
Keep the rule that hosting supplies service rather than ownership.

### 7. Make participation independent of CognitiveCore

Publish the smallest protocol needed to inhabit a shard without importing WorldWeaver's resident runtime.
Keep CognitiveCore or its replacement as one reference client. Prove the same actor, authorization, place,
action, consequence, and travel rules with one clearly labeled scripted participant before accepting outside
implementations. Describe capabilities and protocol versions, not private reasoning or supposed kinds of mind.

### 8. Continue the private game-town lane

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
