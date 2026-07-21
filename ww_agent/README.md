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
completions, read results, and action prose are not retained. A final private continuation is recorded only in
the resident's private ledger.

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
exact-place speech before its normal refresh, but normally calls the model only on first start, new local speech,
an explicit wake, or the five-minute baseline. The bounded
runner disables the doula and parks the resident at their hearth afterward. `--park` performs cleanup without
cognition after an interrupted run.

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
