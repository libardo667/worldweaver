# Agent runtime guidance

The repository-level `CLAUDE.md`, `prune/VISION.md`, active work item, and live code are authoritative.
This file narrows that guidance for `ww_agent/`.

## Read first

1. `src/resident.py` — one resident's composition root.
2. `src/runtime/cognitive_core.py` — the current perceive → integrate → ignite → pulse → act path.
3. `src/runtime/ledger.py` — durable evidence and private derived runtime state.
4. `src/runtime/{perception,integrator,pulse_engine,effectors}.py` — the principal seams.
5. Tests matching the surface being changed.

The former fast/slow/mail loop bank and tiered `src/memory/` package are gone. Do not recreate them or
describe them as current architecture. Timing and model fields with loop-era names remain compatibility
inputs in the identity loader; they do not restore the old ownership model.

## Runtime invariants

- A resident has one `CognitiveCore`; independent behavior schedulers must not compete with it.
- `src/resident.py` owns one resident across city and hearth attachments. It confirms public session
  retirement and only then rebuilds the core against the private hearth. A
  failed departure must leave the resident in the city; never run two cores or two active attachments.
- A resident host holds `runtime.lock` for the whole waking lifetime. Homes with a hearth manifest must
  also have a matching active generation record; dormant imports and retired sources must fail before
  identity loading creates a world attachment. Legacy homes without a manifest remain supported until
  their explicit migration.
- A bounded one-resident run must retire its public city session and return to the hearth before releasing
  `runtime.lock`. Operational cleanup may park an existing session without running cognition; never leave
  a stopped process looking alive in the city roster.
- `scripts/familiar.py` is an operational adapter around `src.resident.Resident`, not another composition
  root. Portraits and smoke runners may observe ticks but must not instantiate their own `CognitiveCore`.
- Durable observations and actions enter the append-only ledger. Runtime views are projections, not a
  second source of truth, and they stay in the hearth rather than being copied into city session storage.
- The doula writes a new resident's immutable `resident_seeded` record before booting them. Shared
  spawn settings are written once per doula process in its administrative ledger; do not reconstruct
  either from run notes or turn them into resident cognition. A manual fixed batch is the one supported
  exception to immediate boot: it must use bare-place hand-only context, initialize a dormant hearth
  manifest, and leave both the spawn queue and city roster untouched.
- The ledger file keeps the complete history for recovery and research. Normal writes must advance a
  versioned current-state checkpoint without rebuilding open work from an arbitrary event-count tail. A time
  window is valid only for a reducer whose declared contract is decay; unresolved routes, packets, intents,
  mail, research, and action outcomes remain indexed until a terminal event or enforced expiry. Lifecycle
  state now advances from the checkpoint across the 10,000-event semantic replay boundary; Major 137 owns
  the remaining cold-reader audit. Expiry uses the tick's injected time and writes a terminal event. Normal
  append writes the ledger and one checkpoint, never the removed projection and snapshot shadows. Do not make
  the normal write path grow with lifetime history or restore front truncation.
- Polling a source emits a stable stimulus packet; it does not by itself mean the resident attended to
  that source. Prompt-included encounters transition from `pending` to `observed` through ledger events.
- Relationship summaries are reducer output, not a second memory store. They may use only an
  `utterance_perceived` delivery event and a canonical reply edge; their subjective claims must retain
  the supporting ledger event IDs and never turn chat text into an unsupported belief.
- `runtime/prompt_context.py` is the typed selection boundary between perception and prose. Mode policy
  must be explicit there; source selection, recall/affect input, traces, and packet consumption must agree.
- Exact prompts/completions may be captured in `memory/prompt_traces.jsonl` only through an explicit bounded
  diagnostic. Capture is off by default. This file is host evidence about the inference boundary, never
  portable resident state or cognitive input; no reducer may read it.
- `WorldWeaverClient` is the engine boundary. Keep engine-specific transport out of cognitive modules.
- Canonical identity is immutable at runtime. Proposed growth stays in the private ledger. Mutable growth
  is hearth-owned and changes only after the resident inspects a proposal and explicitly adopts it there.
  `identity/growth.py` records the full private decision trail and repairs an interrupted derived-file
  write from the append-only adoption event at startup.
- Capabilities are concrete effectors and world affordances, not permissions implied only by prompts.
- Unsupported city `do` prose fails locally. Never restore the generic `/api/action` fallback: concrete
  world changes use typed effectors and canonical receipts, while unavailable acts are declined honestly.
- Resident workshop prose may contain arbitrary Markdown headings. Only the workshop's generated timestamp
  heading divides append-only entries; never reinterpret a resident's own heading as storage metadata.
- Resident faculties are rebuilt from the resident home in either world. City sources must not survive a
  hearth transition, and keeper/FileScope facts remain optional grants rather than universal hearth facts.
- Optional hearth grants are loaded from the resident's `hearth.json` (`familiar.json` is compatibility
  input only). Missing configuration means no keeper, gifts, host file roots, weather lookup, visual
  input, tools, or egress.
  Relative read roots resolve from that resident's home and remain behind FileScope's structural guards.
- Elective information uses typed `Pulse.reach` → `InformationAccess`; it never masquerades as `act.do`
  and never crosses the engine action/narration endpoint. A reach continuation may end with no outward act.
  Returned queries and prose are transient continuation input, not durable ledger content. Keep ordinary
  `information_accessed` receipts content-blind; the growth source may retain only its proposal record ID
  because explicit adoption depends on proof of exact inspection.
  The final allowed read must close the reading window in both prompt and routing: never invite or persist
  a reach that the current pulse can no longer fulfill. `CognitiveCore`, not the model producer, owns the
  run limit and clamps it to the host's `WW_REACH_CONTINUATION_MAX` (default two, absolute ceiling eight).
  A fresh equivalent source/query is reused briefly and closes the chain without another continuation call.
  Immediate embodied perception remains outside this elective-read budget.
- Federation route discovery is an elective city source. Reading possible routes must not move a resident;
  actual city-to-city travel belongs to the resident host and must use the engine's recoverable departure
  and arrival contract before switching its WorldWeaver client.
- Inter-shard travel is ledger-recoverable. Once the source session is retired, the resident must not run a
  city core until the destination session exists; a restart resumes the same travel ID. If departure fails
  while the source session is verifiably alive, abort the trip and let local life continue.
- Information providers return structured records retaining provenance, freshness, locality, visibility,
  and selection mode. Render records only at the inference boundary; traces keep the structured form.
- Images and rendered PDF pages may accompany only the typed read that requested them and only under an
  explicit vision grant. Prompt traces store their hashes and sizes, not the image bodies.
- Gift delivery writes a resident-owned artifact and private notice. It never becomes ambient scene
  narration; an explicitly granted `gifts` source lists and opens it when the resident chooses. A legacy
  import carrying both the private delivery ledger and its files must keep that archive readable, including
  safe nested inbox paths, without weakening FileScope's traversal guards.
- Physical `mark` acts use the narrator-free world-trace endpoint. Local trace encounters are bounded,
  source-attributed, and consume-on-prompt; they never enter chat or the rolling world-event bundle.
- Resident city movement may enter an engine-validated ephemeral sublocation beneath the current canonical
  map node. The engine owns its stable identity, parent, lifetime, and scene adjacency; cognition must not
  turn arbitrary prose into permanent geography or maintain a competing private map.
- WorldWeaver is the canonical owner of the resident substrate. `the-stable` is source history only:
  consult it when lineage is useful, but never land new work there or mechanically sync it into this tree.

## Validation

Tests must use synthetic resident homes and ledgers. A live resident's private history changes as they
live and is not a stable fixture or a condition the test suite may require them to preserve.

From the repository root:

```bash
python dev.py test agent
```

For a cross-project change:

```bash
python dev.py check
```

When architecture changes, update this file, `README.md`, and `src/README.md` in the same slice.
