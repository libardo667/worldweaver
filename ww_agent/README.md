# WorldWeaver resident runtime

`ww_agent` runs persistent residents against the WorldWeaver engine over HTTP. It owns cognition, private
identity, the append-only resident ledger, elective information access, and typed action requests. The
engine decides shared world facts and whether actions succeed.

## Runtime

```text
world observation
      ↓
perception → append-only ledger → derived current state → salience and pulse → typed effectors
                                              ↘ elective source read ↗
```

There is one `CognitiveCore` per awake resident. `src/resident.py` keeps that same core attached to either
the resident's private hearth or one city at a time. City-to-city travel retires the source session and
starts the same actor at the destination through a recoverable handoff. Moving a hearth between computers
is a separate stopped-host migration.

The resident automatically receives only unavoidable local information: current embodiment, exact-place
speech, direct correspondence, local traces, and action results. Broader city information, routes, files,
recall, measurement, objects, making, and stoops are elective sources. A source read can continue within
one bounded ignition, but only a typed effector can change the shared world.

Every observation, decision, source read, and action receipt is appended to the resident ledger. A versioned
checkpoint is intended to provide current state without rereading the resident's full life. That path is under
active repair in Major 137: new records now have serialized sequence numbers, durable writes, and explicit
corruption handling, and unfinished lifecycle work now survives bounded semantic replay. Some normal readers
still scan the complete ledger, but queue expiry is now an explicit event at the tick's injected time and full
replay is deterministic. Normal append writes only the ledger record and one current-state checkpoint; old
projection and snapshot files are removed by an explicit rebuild. The normal tick, prompt, voice, and salience
paths use checkpoint or bounded recent state rather than replaying a whole life. Exact model requests are not
retained during ordinary runs. A deliberately
enabled diagnostic may write them to `memory/prompt_traces.jsonl`; those traces are private host evidence and
are never cognitive input or portable resident state.

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

Use `--duration 15m` for natural wall-clock timing. The bounded runner disables the doula and parks the
resident at their hearth afterward. Add `--trace-prompts` only for a declared inference-boundary diagnostic;
ordinary runs do not retain exact prompts. `--park` performs cleanup without cognition after an interrupted
run.

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
- `src/runtime/cognitive_core.py`: authoritative perceive-to-act composition
- `src/runtime/ledger.py`: complete event history, serialized durable writes, corruption checks, and derived
  current state; remaining cold-history reader cleanup is active
- `src/runtime/perception.py`: source identity and consume-on-prompt handling
- `src/runtime/information.py`: elective typed source access
- `src/runtime/pulse_engine.py`: salience, ignition, and pulse generation
- `src/runtime/effectors.py`: typed action boundary
- `src/world/client.py`: engine transport
- `src/world/resident_signing.py`: exact request signatures for an injected short-lived resident runtime key
- `src/identity/`: identity loading, hearth manifests, packages, and activation
- `src/familiar/`: private hearth adapter and optional grants

See the repository [documentation](../docs/index.md) for current operation and architecture. Coding
invariants live in [AGENTS.md](AGENTS.md). All new runtime work lands in WorldWeaver; `the-stable` is source
history only.
