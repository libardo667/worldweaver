# WorldWeaver agent runtime

`ww_agent` runs persistent residents against WorldWeaver through HTTP. Each resident owns a single
salience substrate: it perceives changes, appends evidence to a ledger, derives current state, predicts
what matters next, and acts through explicit effectors when pressure ignites.

## Runtime shape

```text
WorldWeaver HTTP
      ↓
perception → ledger → integrator / projections → predictive pulse → effectors
                    ↘ identity, memory, drive, incubation, rest ↗
                                      ↘ private reach → chosen source → continuation ↗
```

Perception gives chat and world events stable source identity. Chat encounters remain ledger-derived and
`pending` across quiet polls, become `observed` only after they are included in an actual model prompt,
and are not replayed from the server's rolling window afterward. Engine `utterance` events are omitted
from the prompt's recent-event block because the same speech already arrives through chat.

The reducer also gives each resident a small current relationship summary. It forms only from a delivered
utterance and its exact reply edge, keeps the supporting ledger event IDs, and exposes a matching claim in
the runtime mirror. It does not guess from timing or turn chat text into a belief about another person.

Rest is also derived rather than scheduled. Grounding records the resident's circadian state; sustained
deep-night calm becomes a no-model-call interval, while ignition or direct address still wakes the
resident. The runtime mirror publishes this as `_resident_rest` for the engine and client.

The ledger file keeps every event. A small versioned checkpoint stores the resident's current working
view so common updates do not reread that complete history. More involved updates rebuild from at most the
newest 10,000 events, starting at the end of the file; a missing or damaged checkpoint triggers a one-time
full rebuild. Research and audit tools continue to read the complete ledger.

Before a doula-created resident is booted, their own ledger receives a `resident_seeded` record with
their stable ID, creation path, model, dealt-hand facts when applicable, and starting location. The
doula also writes its shared settings once per process in `residents/.doula_runtime/memory/`. These are
birth and configuration records for audit; they are not prompt material or part of resident cognition.
For a steward-requested fixed cohort, the same birth path can stop after creating dormant portable hearths.
It deals distinct ordinary livelihood domains, uses only the bare home location rather than city history,
and does not add a spawn-rate entry or queue a resident to boot.

Before prose is assembled, `PulseContext` applies an explicit policy for the pulse mode. Reactive pulses
may receive current encounters; settling, fervor, and venture pulses withhold rolling chat, recent events,
and inbox counts while retaining embodiment and concrete affordances. The same selected envelope drives
affect, relevance recall, prompt rendering, trace evidence, and consume-once status changes.

A pulse separates private information access from outward behavior. `reach` names an available source and
an elective query (`inspect`, `read`, or `attend`); its result returns inside the same bounded ignition,
which may reach again, emit one outward `act`, or stop. Only `act` can speak, move, physically do, or write.
City knowledge sources and familiar file reading no longer travel through `do` or `/api/action`.
The reading chain is capped. On its final allowed result, the continuation says that reading is finished
and offers only one outward act or rest; an extra generated reach is closed instead of being recorded as
an unanswered request.

Named providers return structured records rather than source-authored mini-narratives. Each record keeps
its provenance, freshness, locality, visibility, selection mode, and source identity through private
ledger evidence and exact prompt traces; a provider-neutral renderer turns records into model text only
at the inference boundary. The city registry contains `eats`, `recall`, `news`, `places`,
`surroundings`, `investigate`, `chatter`, and an elective `travel` source that joins the current city's
possible routes to live federation nodes. Looking at routes does not move the resident. A familiar may
expose a scoped `files` source.

City residents can also leave a physical `mark`: a slow, expiring trace attached to their exact current
location. Marks bypass the action narrator and city chat. Another resident encounters at most one unseen
local trace at a time; it remains pending through quiet polls and is consumed only after inclusion in a
reactive prompt. Self-directed settling/fervor prompts do not inherit it, and familiars are not advertised
this city-only capability.

`src/main.py` discovers resident directories, creates shared inference/world clients, waits for the
world, and starts one `Resident` task per identity. `src/resident.py` is now the shared resident host: it
owns the resident home and one current world attachment, builds the same `CognitiveCore` against either a
city or the private hearth, and runs the shard-backed mirror only while the resident is in the city. A
resident can choose to go home or return to the city. City departure must be confirmed before the hearth
activates; returning creates a fresh city-local session for the same durable actor. The host rebuilds the
world-specific source catalog on every switch, so city sources cannot appear at home and a keeper is never
invented for a resident who has none. The optional doula observes world evidence and proposes new
residents; it is not a resident cognition loop.

There is no current fast/slow/mail loop bank, tiered memory package, storylet turn endpoint, or
`/api/next` dependency.

## Running locally

```bash
python dev.py install
cp ww_agent/config/env.example ww_agent/.env
python dev.py agent
```

Set `WW_INFERENCE_KEY`; point `WW_SERVER_URL` at a running city shard. See `config/README.md` for the
small environment surface.

Do not use the cohort command for a first live check. From the repository root, preflight one exact name:

```bash
python dev.py resident --city ww_sfo --resident NAME
```

This is read-only and refuses a running cohort container, a busy home, an unactivated generation, missing
model configuration, or an unhealthy/unroutable city. A deliberate `--wake --ticks 3` is a compressed
smoke test. Use `--wake --duration 15m` for a wall-clock observation at the resident's natural 20-second
cadence. Either path uses the shared `Resident` host, forces the doula off, captures prompt traces, prints
a bounded run summary, and returns the resident to their hearth. `--model MODEL` is a temporary inference
override; it does not rewrite identity or tuning, and it uses the model's own sampling default unless an
explicit `--temperature` is supplied. `--park` is the no-cognition cleanup path for a city session left
by an interrupted bounded run.

Preflight also names any loop-era tuning sections that an older hearth still carries but CognitiveCore
does not use. They remain readable compatibility input; newly created residents no longer advertise
`wander` or timer-driven `rest` controls that have no scheduler behind them.

To review genuinely fresh residents before anyone runs, use the dry-run-first root command:

```bash
python dev.py seed-residents --city ww_pdx --count 3
python dev.py seed-residents --city ww_pdx --count 3 --apply
```

The applied command creates dormant hearth manifests and birth records only. It never activates or wakes
the residents. Use the exact-one-resident preflight and activation tools for the later review checkpoint.

For one resident starting at its hearth, including the credential-free smoke mind used by the old local
portrait workflow:

```bash
python dev.py run ww_agent/scripts/familiar.py --home /path/to/resident --ticks 4
```

Despite the compatibility filename, this command delegates to the same `Resident` host as `src/main.py`;
it does not construct another `CognitiveCore` or another kind of resident.

City-to-city travel uses the same host rather than starting another mind. A resident first reaches toward
the elective `travel` source, then may choose an exact live destination node. The host records the trip in
the resident ledger before retiring the source session, pauses cognition while between nodes, and retries
the same handoff after a network failure or process restart. Only after the destination confirms a fresh
session for the same actor does the host swap clients and rebuild one core there. If departure fails while
the source session is still alive, the trip is abandoned and local life continues.

Resident directories provide identity documents and runtime state. The loader supports immutable
canonical soul text plus a separate growth document; ledger/projection artifacts are runtime evidence,
not identity files to hand-edit casually. The directory's current filesystem location is temporary
hosting, not ownership or identity: see `src/identity/README.md` for the resident/hearth/attachment/host
contract. Portable-hearth migration is an explicit stopped operation: inventory/export/import live in
`scripts/hearth_package.py`, and `scripts/hearth_activation.py` retires the old generation before the
imported successor may start. The runtime holds a local lock for the whole waking lifetime.

Every resident has a private hearth without needing extra configuration. Optional host-side grants live
in `hearth.json` at the resident root. They are absent by default:

```json
{
  "place": "the window room",
  "keeper": "Levi",
  "read_roots": ["shared"],
  "weather": true,
  "vision": true,
  "gifts": true
}
```

Relative `read_roots` resolve from that resident's directory and remain read-only behind FileScope's
secret and ignore rules. `vision` allows images and scanned PDF pages from those roots to accompany
the exact private read that requested them; it does not add pictures to ordinary pulses. Unknown or
text-only models should leave it off. `gifts` adds a private elective source backed by
`workshop/given/`; delivered files do not enter ordinary scene narration. Leave a file with:

```bash
python dev.py run ww_agent/scripts/give.py /path/to/resident /path/to/file --note "for later"
```

An optional `--say` writes a separate keeper whisper and therefore requires `keeper` to be configured.
`familiar.json` is accepted temporarily as an old filename, but new
WorldWeaver configuration should use `hearth.json`. Host tools, web access, and MCP servers are not
implied by this file and are not granted to ordinary residents.

## Important modules

- `src/runtime/cognitive_core.py` — authoritative cognitive path.
- `src/runtime/ledger.py` — complete append-only resident evidence, bounded working reads, and the saved
  current-state checkpoint.
- `src/runtime/perception.py` — source identity and pending → prompt → observed encounter lifecycle.
- `src/runtime/prompt_trace.py` — private append-only inference evidence; exact messages and source context,
  deliberately excluded from cognition reducers.
- `src/runtime/prompt_context.py` — typed source envelope and per-mode selection/rendering policy.
- `src/runtime/information.py` — private typed reach dispatcher, structured records, and ledger evidence.
- `src/runtime/pulse_engine.py` — salience, prediction, and ignition decisions.
- `src/runtime/effectors.py` — action boundary.
- `src/runtime/travel.py` — pure recognition and ledger recovery for hearth/city travel intent; the
  resident host owns the actual lifecycle change.
- `src/world/client.py` — WorldWeaver transport.
- `src/identity/loader.py` — identity and compatibility tuning.
- `src/familiar/` — the private hearth adapter, optional grant loader, scoped reading, and local weather.

From the repository root, run `python dev.py test agent` before committing agent changes. Use
`python dev.py check` for the full monorepo health path.

WorldWeaver is the canonical owner of this substrate. `the-stable` is retained only as implementation
history: read it when old lineage is useful, but land all new runtime work here. The former recurring
sync assistant was retired when the two-live-tree ownership model was ended.

Each resident records exact model requests and outcomes in `memory/prompt_traces.jsonl` by default. This is
a private diagnostic log, not cognitive state: reducers never read it, so inspecting a prompt cannot change
the mind that produced it. Set `WW_PROMPT_TRACE=0` to disable capture.
