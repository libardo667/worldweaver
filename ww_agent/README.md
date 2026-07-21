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
active runtime generation, current city or hearth attachment, reference-adapter version, selected model ID,
and acknowledged local-speech cursor. Loading the checkpoint for a different actor or hearth, or moving it
backward to an older generation, fails instead of quietly reusing the state. The current API-backed model has
no portable hidden state, so the envelope says exactly that: format `none`, zero bytes. It does not pretend a
chat completion is an uninterrupted process. A later recurrent adapter must declare its own bounded format.

Each continuation also chooses a return between one minute and seven days and whether exact-place speech may
offer an earlier model turn. While that return is in the future, it replaces the ordinary five-minute model
baseline. Speech is still delivered and acknowledged when early activation is disabled; the host simply does
not turn delivery into a forced inference call. A due return is consumed and its activation time checkpointed
in one transition, so restarting cannot repeatedly spend the same scheduled opportunity.

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
- `src/runtime/information.py`: elective typed source access
- `src/runtime/effectors.py`: typed action boundary
- `src/world/client.py`: engine transport
- `src/world/resident_signing.py`: host-sealed identity to renewable, generation-bound runtime request signing
- `src/identity/`: identity loading, hearth manifests, packages, and activation
- `src/familiar/`: private hearth adapter and optional grants

See the repository [documentation](../docs/index.md) for current operation and architecture. Coding
invariants live in [AGENTS.md](AGENTS.md). All new runtime work lands in WorldWeaver; `the-stable` is source
history only.
