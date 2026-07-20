# WorldWeaver resident runtime

`ww_agent` runs persistent residents against the WorldWeaver engine over HTTP. It owns cognition, private
identity, the append-only resident ledger, elective information access, and typed action requests. The
engine decides shared world facts and whether actions succeed.

## Runtime

```text
poll current place and local speech
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

Use `--duration 15m` for natural wall-clock timing. The resident polls every twenty seconds but normally calls
the model only on its first poll, new local speech, an explicit wake, or the five-minute baseline. The bounded
runner disables the doula and parks the resident at their hearth afterward. `--park` performs cleanup without
cognition after an interrupted run.

Create fresh dormant residents with a dry run first:

```bash
python dev.py seed-residents --city ww_alderbank --count 4
python dev.py seed-residents --city ww_alderbank --count 4 --apply
```

Creation does not activate, wake, or place them in the city.

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
