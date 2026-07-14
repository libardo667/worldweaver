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
`investigate`, and `chatter`, while a familiar may expose a scoped `files` source.

`src/main.py` discovers resident directories, creates shared inference/world clients, waits for the
world, and starts one `Resident` task per identity. `src/resident.py` composes each `CognitiveCore` and
its runtime mirror. The optional doula observes world evidence and proposes new residents; it is not a
resident cognition loop.

There is no current fast/slow/mail loop bank, tiered memory package, storylet turn endpoint, or
`/api/next` dependency.

## Running locally

```bash
cd ww_agent
python -m pip install -e '.[dev]'
cp config/env.example .env
python -m src.main
```

Set `WW_INFERENCE_KEY`; point `WW_SERVER_URL` at a running city shard. See `config/README.md` for the
small environment surface.

Resident directories provide identity documents and runtime state. The loader supports immutable
canonical soul text plus a separate growth document; ledger/projection artifacts are runtime evidence,
not identity files to hand-edit casually.

## Important modules

- `src/runtime/cognitive_core.py` — authoritative cognitive path.
- `src/runtime/ledger.py` — append-only resident evidence.
- `src/runtime/perception.py` — source identity and pending → prompt → observed encounter lifecycle.
- `src/runtime/prompt_trace.py` — private append-only inference evidence; exact messages and source context,
  deliberately excluded from cognition reducers.
- `src/runtime/prompt_context.py` — typed source envelope and per-mode selection/rendering policy.
- `src/runtime/information.py` — private typed reach dispatcher, structured records, and ledger evidence.
- `src/runtime/pulse_engine.py` — salience, prediction, and ignition decisions.
- `src/runtime/effectors.py` — action boundary.
- `src/world/client.py` — WorldWeaver transport.
- `src/identity/loader.py` — identity and compatibility tuning.
- `src/familiar/` — scoped local capabilities shared with the familiar substrate.

Run `.venv/bin/python -m pytest tests -q` before committing agent changes. For the full monorepo health
path, run `python scripts/dev.py check` from `worldweaver_engine/`.

The substrate is periodically reconciled from `the-stable` with `scripts/sync_substrate.py`. Always run
`--dry-run` first and obey `scripts/substrate_sync_manifest.toml`; the tool stages changes for review and
does not commit them.

Each resident records exact model requests and outcomes in `memory/prompt_traces.jsonl` by default. This is
a private diagnostic log, not cognitive state: reducers never read it, so inspecting a prompt cannot change
the mind that produced it. Set `WW_PROMPT_TRACE=0` to disable capture.
