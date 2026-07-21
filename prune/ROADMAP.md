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
- a completed name-only Levi run showing that the small loop can notice live human speech, use shared world
  actions, and park cleanly, with two prompt-pipeline leaks found and fixed afterward;
- a completed post-audit Mira run showing grounded use of attributed public marks, no forced reply, and a
  concrete failure to remember her own recent confirmed actions;
- citywide speech absent from automatic perception, with its former elective source withheld until the
  engine has an explicit writable citywide channel;
- durable objects, making, giving, exchange, room access, and bounded object stoops;
- a fictional test town, Alderbank, with four game-native resident homes and bounded human/resident play;
- a place-centered public client;
- recoverable local city-to-city handoff;
- a synthetic human round trip between separately isolated Ubuntu VM hosts, with exactly one final presence;
- one isolated public Alderbank node and one closed directory using separate signed node identities;
- one completed one-hour, four-resident Alderbank baseline with clean hearth parking;
- stopped hearth export, import, and generation fencing;
- hearth-owned identity growth with private inspect-then-adopt decisions and complete provenance;
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

The live human client now sends its login token on participant-scoped reads. Before that repair, the server
correctly rejected requests for marks, objects, making, exchanges, stoops, and doorway state, but the client
often turned the failure into an empty panel. Public and resident affordances must continue to share engine
contracts even when their controls look different.

## Now

### 1. Finish the human-surface split

Make `client-public` the normal participant interface. Keep the older combined client only for justified
steward/debug functions or retire it. Do not copy resident telemetry into the public client. Close the
remaining ordinary-action gaps: correspondence, safe encounter targets for direct gifts, and deliberate
human creation of temporary sublocations. Make the current place and its verb palette the default view;
keep the map as an optional full-screen orientation and destination surface.

### 2. Keep the small resident runtime as the control

The resident host now uses the fresh reference loop rather than `CognitiveCore`. It polls the exact place and
local speech, activates on a new local signal or slow baseline, permits one elective read, and then accepts one
typed action, private continuation, or wait. It has no production salience, arousal, prediction, drive,
incubation, embedding, or mixed-pulse policy. Quiet is a valid result rather than a diagnosed failure.

The ledger/checkpoint repair is complete, automatic Doula creation is off, and the old model-written batch
creator can no longer apply changes. A disposable signed resident has completed real Alderbank bootstrap,
protected scene access, and clean leave with no model or prose involved. The supported creator now makes one
reviewable resident at a time with only a chosen name, empty ledger, dormant hearth, public identity card, and
host-sealed key.

The elective information audit is also complete. The live prompt now shows source egress, provenance,
freshness, locality, and visibility before a resident chooses, and repeats that context with returned records.
The reference loop does not cache reads by default, canonical ledger keepsakes are reachable through recall,
and file images reach only the chosen after-read call. `Investigate`, public RSS `news`, and citywide `chatter`
are withheld until typed history, resident-scoped network grants, and a real citywide channel exist.

That first run is now complete. Levi used an empty ledger and name-only identity, responded promptly to live
human speech, and parked cleanly. It also exposed two prompt-pipeline leaks: archived room chat was treated as
live hearing on entry, and the prompt pipeline supplied attention-themed language that echoed into public
speech. Both are now removed and pinned by synthetic tests. A second fresh resident, Rowan, then proved the
durable live-speech path with two signed messages, prompt activation within 0.02 seconds, acknowledgement after
observation, no self-reply loop, timer fallback, and clean parking. That run found one remaining archive leak:
speech also entered the prompt as a copied world event. A deeper scene audit then found that the engine itself
turned weather, time, headcount, event count, and city-pack mood prose into invented social scenery. Its
event-count rule supplied Rowan's exact phrase “ripples of attention.” Those automatic history and narration
routes are now removed. Minor 33 owns a later typed environmental-fact replacement. Rowan's wording is not a
clean post-fix language sample. Keep this loop available as the simple comparison and rollback path while the
next resident process is built; do not make visible activity the pass condition.

A fresh post-fix resident, Mira, then ran for 15 minutes with only a name and empty ledger. Her references to
history and walls were grounded in exact, attributed public marks already present at Commons Bank rather than
engine-authored mood. She also left two marks and later incorrectly told a human that she had left none. The
current scene omits the viewer's own marks, and independent model calls carry no bounded record of confirmed
recent actions. Treat this as a direct input to Major 141: add typed self-action continuity, not a prose recap
or a restored narrator.

Continue the research audit as a separate evidence lane. It should explain why old mechanisms remain removed
or earn re-entry, not tune the new loop toward sociability, movement, or a preferred personality.

### 3. Deliver live signals and prototype a persistent resident process

First, separate event delivery from the resident's decision to respond. Add durable cursors and an
interruptible wait for exact-place events, resident-set timers, pause, reconnect, and travel. Direct speech
may offer an earlier activation; it may not force one public action. Keep the current poll as the control until
the event path proves ordering, retention, isolation, and cleanup. The first exact-place speech cursor,
interruptible wait, observation acknowledgement, timer fallback, and same-session restart record are now in
place. Major 132 owns the remaining signal families, fault measurements, and broader cleanup proof.

Then implement Major 141's smallest local, checkpointable resident process. Carry bounded resident-specific
state from one activation to the next, support open private activities and resident-chosen return times, and
fence stale results when the world changes during inference. Begin with one synthetic resident and one
open-weight model. Do not restore CognitiveCore under new names, generate an endless inner monologue, or claim
that process continuity proves a human-like inner life.

Major 141's first slice is now in place. The existing private checkpoint retains a bounded typed view of
confirmed own actions, and a rebuilt reference core can recover exact action kind, place, target, time, and
stable identifiers without receiving action prose. A synthetic mark survives core destruction and rebuild.
The second slice gives one explicitly continued private activity a stable ID, exact bounded resident-authored
description, deterministic checkpoint replay, and explicit completion. It survives a rebuilt core without
being reconstructed from recent prose and stays isolated to its hearth. The third slice adds a chosen return
between one minute and seven days, an optional `local_speech` early-wake class, restart-safe activation timing,
and a host boundary where delivery is no longer a forced model call. The fourth slice versions the structural
observation and private process behind every activation, discards stale state-changing choices after a final
recheck, and keeps the retry pending across restart. Next, finish the explicit process-checkpoint envelope—
resident, hearth generation, attachment, adapter/model version, cursor, and bounded model-state format. That
fifth slice is now complete. The current adapter honestly binds a zero-byte `none` model state, while the same
checkpoint restores its activity, return, action receipts, retry flag, cadence, and exact-session event cursor.
Wrong-resident and wrong-hearth loads or generation regressions fail closed. The portable ledger rebuilds the
derived checkpoint after host transfer. A sixth slice now records hosted and cleanly suspended intervals, the
measured gap on restore, and an explicitly unknown gap after an unclean stop. Next, define and measure the
smallest bounded recurrent adapter state before plugging in an open-weight prototype; do not substitute a
provider chat transcript or unlimited cache.

### 4. Add the private-to-public making boundary

Let a person or resident deliberately share a bounded note or made file at one place. Record authorship,
source, license, publication choice, media type, size, time, and expiry. Do not build a global feed or expose
private workshops. Separately, give hearths a real object store so a resident can deliberately make one
physical possession, choose to carry it into a city, and leave that same object at a stoop without prose
creating resources or travel duplicating it.

### 5. Finish the public-node proof

Independent node identities, signed requests, HTTPS ingress, and the first `world-weaver.org` directory/node
have been proven on one computer. The checked-in shard backends bind to loopback by default, the public
readiness response does not expose internal federation addresses or resident-inference configuration, and the
live client serves built static assets rather than Vite development mode. A synthetic human has also completed
a full round trip between two isolated Ubuntu VM hosts over a private link. Next, test an encrypted off-device
restore, add folder-local resident operation, and repeat entry and travel between separately administered HTTPS
computers or trust domains.

## Next

### 6. Make participation independent of the resident runtime

Publish the smallest protocol needed to inhabit a shard without importing `ww_agent`. Prove the same actor,
authorization, place, action, consequence, live-signal, and travel rules with one clearly labeled scripted
participant. The reference loop and later persistent model are clients of this protocol, not definitions of
who may participate.

### 7. Build the multi-timescale resident gym

Use Major 142 to exercise production world rules under an injected clock. Keep live conversations and races
at measured interactive speed, skip quiet intervals, and fork synthetic checkpoints to compare later
consequences. Use scripted background actors where possible and score separate software competencies—not
speech, movement, compliance, or engagement. Publish held-out scenarios before using the gym to improve a
model. The prerequisite extraction is complete for the first scenario: movement, local speech, session
lifecycle, and recoverable signed travel sit below HTTP beside the existing object, making, access, exchange,
and stoop services.

The first deterministic service-level episode now runs with `python dev.py gym`. A scripted participant and a
mechanical listener share a place, exchange speech, separate, prove that old-place speech does not follow the
listener, and reunite. Every state change and signal read uses production services, and a factual terminal and
browser view make the run inspectable without adding narration. An automated FastAPI replay now uses two
separately registered actors, refuses anonymous access, and matches the service run's chat rows, world events,
and final locations. That proves in-process HTTP parity, not container or network behavior.

The repaired correspondence boundary is now covered by `python dev.py gym --episode waiting-letter`. Mail uses
durable actor IDs and exact authentication, survives a temporary session change, remains pending across repeated
reads, and is consumed only by explicit acknowledgement after processing. The reference resident follows the
same delivery rule. Cross-shard mail and a human correspondence interface remain open. The next gym slice is an
injected production clock and one mixed-time episode; accelerated model calls still come later.

### 8. Train several resident model families

After the gym and baselines exist, use Major 143 to teach open-weight models the WorldWeaver interface and
long-timescale consequence structure. Start with small, versioned substrate adapters over more than one base
model. Use only synthetic or explicitly licensed training material, preserve multiple valid choices, and
reject one scalar definition of the best resident. Personal learning remains disabled until consent,
portability, poisoning resistance, capability retention, and rollback are real.

### 9. Finish City Studio

Build a browser editor over the existing city-pack builder and validator. Support drafts, deterministic
field-and-section map generation from Major 131, preview, export, and deliberate publication before
habitation. Do not mutate an inhabited pack without a migration plan.

### 10. Finish resident portability and recovery

Add host authorization, address rotation, recovery from an unavailable host, and independent-node tests.
Keep the rule that hosting supplies service rather than ownership.

### 11. Continue the private game-town lane

Use Alderbank to test understandable consequences over multiple sessions. Keep game rules opt-in and
constructive. Do not turn game telemetry into general resident assessment.

## Later

- measured local-model serving, batching, and cost reduction after model quality is established;
- source verification for explicitly epistemic roles;
- private correspondence refinements;
- durable spend and energy accounting;
- additional public cities and discovery models.

Experiments, publication tasks, and completed work are intentionally absent from this list. See
[`prune/README.md`](README.md) for those lanes.
