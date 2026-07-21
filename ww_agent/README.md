# WorldWeaver resident runtime

`ww_agent` runs persistent residents against the WorldWeaver engine over HTTP. It owns cognition, private
identity, the append-only resident ledger, elective information access, and typed action requests. The
engine decides shared world facts and whether actions succeed.

## Runtime

```text
wait for local speech or the normal timer, then observe the current place
      ↓ when first started, newly addressed, explicitly woken, or baseline is due
one model choice → optional single source read → final choice → typed effector or quiet
```

There is one `ReferenceResidentCore` per awake resident. `src/resident.py` keeps that same resident attached
to either their private hearth or one city at a time. City-to-city travel retires the source session and
starts the same actor at the destination through a recoverable handoff. Moving a hearth between computers is
a separate stopped-host migration. The older `CognitiveCore` remains as non-production comparison code while
useful pieces are evaluated individually.

The resident automatically receives only current-place facts and exact-place speech. Broader city information,
routes, files, objects, making, and stoops are elective sources. One activation may read one source before its
final choice, but only a typed effector can change the shared world.

The ledger holds durable lifecycle evidence and content-blind inference, information, and action receipts. A
versioned checkpoint provides current state without rereading the resident's full life. Records have serialized
sequence numbers, durable writes, explicit corruption handling, deterministic replay, and open-work indexes
that survive bounded history. An ordinary reference-loop tick does not parse cold history. Exact prompts,
completions, read results, and action prose are not retained. A final private continuation is recorded in the
resident's private ledger and reduced into one open checkpoint record. That record carries a generated ID and
the resident's own bounded description. It survives a rebuilt core, retains its ID when continued, remains
open while the resident waits or acts, and closes only when the resident explicitly finishes it. It is not
copied into city state, expanded into a hidden task queue, or reconstructed from old unversioned prose.

That checkpoint now has an explicit process envelope. It names the durable actor, authoritative hearth and
active runtime generation, current city, hearth, or in-transit attachment, reference-adapter version, selected model ID,
and acknowledged local-speech cursor. Loading the checkpoint for a different actor or hearth, or moving it
backward to an older generation, fails instead of quietly reusing the state. The current API-backed model has
no portable hidden state, so the envelope says exactly that: format `none`, zero bytes. It does not pretend a
chat completion is an uninterrupted process. A later recurrent adapter must declare its own bounded format.

The envelope also distinguishes a running host interval from a cleanly suspended process. Each run gets a
random structural ID. A clean stop records when hosting ended, and the next start records the measured stopped
interval. If a process restarts without a matching clean-stop record, the prior stop time is marked unknown and
no elapsed downtime is invented. These records describe software operation, not continuous thought or
experience while the computer was off.

The synthetic resident gym can bind that private process to the engine without importing agent code into the
engine process. It uses the existing deterministic portable hearth package as an externally held artifact. The
engine checkpoint receives only its format, ID, byte count, and digest. A separate agent process verifies those
bytes, imports into staging, rebuilds the derived checkpoint from the append-only ledger, checks the exact
resident/process binding, and only then installs the restored home. This is a local synthetic restart proof,
not authorization to clone or wake an existing resident.

Each continuation also chooses a return between one minute and seven days and whether exact-place speech may
offer an earlier model turn. While that return is in the future, it replaces the ordinary five-minute model
baseline. Speech is still delivered and acknowledged when early activation is disabled; the host simply does
not turn delivery into a forced inference call. A due return is consumed and its activation time checkpointed
in one transition, so restarting cannot repeatedly spend the same scheduled opportunity.

The host-facing return operation is explicitly at-least-once. An offered event must match the stable ID derived
from actor, private activity ID, and deadline, and it cannot be handled before that deadline. Consumption writes
a content-free receipt before inference begins. If the resident process stops after that write but before the
host receives its answer, the repeated offer returns `already_processed` without another model call. The receipt
contains the return ID, activity ID, deadline, and consumption time—not the private activity description.
The resident gym now proves that rule across the engine/agent process boundary. It restores a synthetic hearth,
passes a scene built by the same service as the live scene API, deliberately loses the first engine
acknowledgement, and verifies that the retry performs zero additional model calls. The fixture model always
chooses `wait`; this is a restart and custody test, not evidence of resident capability.

The model-backed gym path extends that boundary with a generic versioned stdio byte transport. A separate child
process runs the normal `Resident` host, an OpenAI-compatible model client, and the ordinary signed
`WorldWeaverClient`; its exact HTTP requests return to the parent and enter the actual FastAPI application over
the synthetic gym database. The host takes and releases the synthetic hearth's normal exclusive lease, resumes
the bound city session, reads the node's public experience and city-pack profile, and constructs the same city
source registry as an ordinary resident. The child never owns the engine database, and the structural stream carries
inference boundaries and aggregate usage rather than
prompts, completions, elective queries, or private source results. After activation, the stopped synthetic
hearth is exported again so a later gym checkpoint binds the state that actually produced the result. The
deterministic model proof now requests travel home, crosses the signed city leave route, and restarts in a
second child process at the real `LocalWorld` attachment. That restart observes only the hearth registry and
does not spend another model call.

Hearth departure is an idempotent cross-process transition. The host records one stable transition ID before
calling the city. The city atomically retires the session and stores a receipt bound to that transition,
session, actor, and runtime generation. If the request, commit, response, or resident process fails, restart
retries the same transition rather than rerunning the model choice. A committed response replay returns the
original receipt; mismatched actors, generations, sessions, and transition IDs are refused. `LocalWorld` is
constructed only after the private process checkpoint says hearth.

The stdio hop is process transport, not a second world API or resident composition root. A bounded scheduled
return method on `Resident` owns the exact appointment, process interval, attachment wrapper, core, and custody
release. The model gym exercises normal HTTP resident proof, including shard discovery,
runtime-certificate signing, city admission, generation/session binding, verification, and nonce consumption.
It now exercises both the node-published commons source registry and its replacement by the private hearth
registry after confirmed departure. It still does not enable optional constructive-game capabilities, contact
federation, or cross a listening network socket; its episode fidelity metadata names those gaps.

Resident world time is explicit at the host boundary. Production hosts default to real UTC. A controlled gym
activation injects the same world instant into normal reference-core ticks and `LocalWorld` grounding, whisper
freshness, scene events, private reads, and voice records. Runtime leases, retry sleeps, certificate validity,
request nonces, inference latency, and measured process duration retain their real or monotonic clocks.

Each model activation is also tied to structural versions of what the resident was shown and the private
checkpoint state it began from. After the final model response, the adapter checks the current place and
checkpoint again. A changed location, presence set, new speech ID, trace set, route, source declaration, or
private activity structure prevents an outward action or private activity update from using the old answer.
The discarded choice is not stored; the checkpoint records only the activation ID, versions, change classes,
and a pending retry. A quiet `wait` remains harmless, while the new facts still receive another opportunity.
Typed engine endpoints continue to decide whether a mechanically current action succeeds.

The checkpoint now also retains the newest twelve confirmed reference-loop actions as typed receipts. A newly
built reference core loads them and may show the newest five as exact kind, place, target, time, and stable
world identifiers. This lets a resident recover ordinary facts such as having recently left a mark without
storing the mark's prose or asking the city to hold private continuity. Declined, unknown, and older untyped
action records are not promoted into that view.

## Run from the repository root

Install and test:

```bash
python dev.py install
python dev.py test agent
```

Inspect one resident without waking them:

```bash
python dev.py resident --city ww_alderbank --resident NAME
```

After reviewing the preflight, a bounded wake is explicit:

```bash
python dev.py resident --city ww_alderbank --resident NAME --wake --ticks 3
```

Use `--duration 15m` for natural wall-clock timing. In a city, the resident waits up to twenty seconds for new
exact-place speech before its normal refresh. The model is called when its baseline or chosen return is due,
when an eligible local-speech event arrives, or after an explicit wake. A recent activation time survives core
rebuild, so restart alone is not another model turn. The same checkpoint restores the live-speech cursor only
for the exact city session to which it was bound. The bounded runner disables the doula and parks the resident
at their hearth afterward. `--park` performs cleanup without cognition after an interrupted run.

Create one plain resident with a dry run first:

```bash
python dev.py create-resident --city ww_alderbank --name "Robin Vale"
python dev.py create-resident --city ww_alderbank --name "Robin Vale" --apply
```

Creation writes only the chosen name and structural hearth files. It does not call a model, assign a biography
or job, start a ledger, activate, wake, or place the resident in the city. It creates a public identity card
and seals the private identity key for the current hearth host. A steward must separately review and admit the
public card, then activate the hearth, before the resident can use signed city bootstrap.

## Resident homes

An initialized home has a stable actor ID and hearth manifest. Resident-owned identity, ledger evidence,
and workshop files are portable; city sessions, host paths, credentials, caches, and host grants are not.
Export/import and runtime-generation tools live under `scripts/hearth_*.py` and fail closed while a resident
is awake.

Optional host grants live in `hearth.json` and are absent by default. They may enable scoped read roots,
weather, vision for a requested image/PDF read, or private gifts. They do not imply web access, arbitrary
host tools, or MCP access. `familiar.json` and `scripts/familiar.py` remain compatibility names for older
hearths; they use the same `Resident` host and do not define a second kind of person.

## Code map

- `src/resident.py`: resident lifetime, hearth/city attachment, and travel recovery
- `src/runtime/reference_core.py`: production poll, one-read, and final-choice loop
- `src/runtime/cognitive_core.py`: non-production audited predecessor retained for selective salvage
- `src/runtime/ledger.py`: complete event history, serialized durable writes, corruption checks, and derived
  current state; remaining cold-history reader cleanup is active
- `src/runtime/private_artifact.py`: content-safe gym binding and staged private artifact restore
- `src/runtime/information.py`: elective typed source access
- `src/runtime/effectors.py`: typed action boundary
- `src/world/client.py`: engine transport
- `src/world/resident_signing.py`: host-sealed identity to renewable, generation-bound runtime request signing
- `src/identity/`: identity loading, hearth manifests, packages, and activation
- `src/familiar/`: private hearth adapter and optional grants

See the repository [documentation](../docs/index.md) for current operation and architecture. Coding
invariants live in [AGENTS.md](AGENTS.md). All new runtime work lands in WorldWeaver; `the-stable` is source
history only.
