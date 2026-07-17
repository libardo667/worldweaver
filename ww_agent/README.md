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

Before prose is assembled, `PulseContext` applies an explicit policy for the pulse mode. Reactive pulses
may receive current encounters; settling, fervor, and venture pulses withhold rolling chat, recent events,
and inbox counts while retaining embodiment and concrete affordances. The same selected envelope drives
affect, relevance recall, prompt rendering, trace evidence, and consume-once status changes.

A pulse separates private information access from outward behavior. `reach` names an available source and
an elective query (`inspect`, `read`, or `attend`); its result returns inside the same bounded ignition,
which may reach again, emit one outward `act`, or stop. Only `act` can speak, move, physically do, or write.
City knowledge sources and familiar file reading no longer travel through `do` or `/api/action`.

Named providers return structured records rather than source-authored mini-narratives. Each record keeps
its provenance, freshness, locality, visibility, selection mode, and source identity through private
ledger evidence and exact prompt traces; a provider-neutral renderer turns records into model text only
at the inference boundary. The initial city registry contains `eats`, `recall`, `news`, `places`,
`surroundings`, `investigate`, and `chatter`, while a familiar may expose a scoped `files` source.

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

Resident directories provide identity documents and runtime state. The loader supports immutable
canonical soul text plus a separate growth document; ledger/projection artifacts are runtime evidence,
not identity files to hand-edit casually.

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
- `src/runtime/travel.py` — pure recognition of hearth/city travel intent; the resident host owns the
  actual lifecycle change.
- `src/world/client.py` — WorldWeaver transport.
- `src/identity/loader.py` — identity and compatibility tuning.
- `src/familiar/` — scoped local capabilities shared with the familiar substrate.

From the repository root, run `python dev.py test agent` before committing agent changes. Use
`python dev.py check` for the full monorepo health path.

WorldWeaver is the canonical owner of this substrate. `the-stable` is retained only as implementation
history: read it when old lineage is useful, but land all new runtime work here. The former recurring
sync assistant was retired when the two-live-tree ownership model was ended.

Each resident records exact model requests and outcomes in `memory/prompt_traces.jsonl` by default. This is
a private diagnostic log, not cognitive state: reducers never read it, so inspecting a prompt cannot change
the mind that produced it. Set `WW_PROMPT_TRACE=0` to disable capture.
