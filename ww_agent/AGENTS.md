# Agent runtime guidance

The repository-level `CLAUDE.md`, `prune/VISION.md`, active work item, and live code are authoritative.
This file narrows that guidance for `ww_agent/`.

## Read first

1. `src/resident.py` — one resident's composition root.
2. `src/runtime/reference_core.py` — the production poll → optional read → final choice path.
3. `src/runtime/ledger.py` — durable evidence and private derived runtime state.
4. `src/runtime/{information,effectors}.py` — the current read and action seams.
5. Tests matching the surface being changed.

The former fast/slow/mail loop bank and tiered `src/memory/` package are gone. Do not recreate them or
describe them as current architecture. Timing and model fields with loop-era names remain compatibility
inputs in the identity loader; they do not restore the old ownership model.

## Runtime invariants

- A resident has one `ReferenceResidentCore`; independent behavior schedulers must not compete with it.
  `CognitiveCore`, perception, integration, salience, prediction, and pulse generation are audited legacy
  mechanisms, not the production path. Do not reconnect one without an explicit work item and paired proof.
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
  root. Portraits and smoke runners may observe ticks but must not instantiate their own resident core.
- Durable observations and actions enter the append-only ledger. Runtime views are projections, not a
  second source of truth, and they stay in the hearth rather than being copied into city session storage.
- Normal resident creation is model-free and one-at-a-time. It writes a chosen name, stable ID, dormant
  hearth manifest, public identity card, and host-sealed signing key while leaving the private ledger empty.
  City admission, activation, and waking are separate operator acts. The old Doula and its model-written
  batch creator are comparison and migration code, not the supported creation path.
- The ledger file keeps the complete history for recovery and research. Normal writes must advance a
  versioned current-state checkpoint without rebuilding open work from an arbitrary event-count tail. A time
  window is valid only for a reducer whose declared contract is decay; unresolved routes, packets, intents,
  mail, research, and action outcomes remain indexed until a terminal event or enforced expiry. Lifecycle
  state now advances from the checkpoint across the 10,000-event semantic replay boundary; Major 137 owns
  the remaining cold-reader audit. Expiry uses the tick's injected time and writes a terminal event. Normal
  append writes the ledger and one checkpoint, never the removed projection and snapshot shadows. Do not make
  the normal write path grow with lifetime history or restore front truncation.
- The production loop polls current-place facts and local public speech. Polling is not a model activation;
  first start, new local speech, an explicit wake, or the slow baseline activates the model. Do not replay old
  speech as new at every baseline.
- Relationship summaries are reducer output, not a second memory store. They may use only an
  `utterance_perceived` delivery event and a canonical reply edge; their subjective claims must retain
  the supporting ledger event IDs and never turn chat text into an unsupported belief.
- The production reference loop does not store exact prompts or completions. `runtime/prompt_context.py` and
  `runtime/prompt_trace.py` belong to the old core; no reducer may read old diagnostic traces.
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
- Elective information uses one typed read through `InformationAccess`; it never masquerades as `act.do`
  and never crosses the engine action/narration endpoint. A read may end with no outward act.
  Returned queries and prose are transient final-call input, not durable ledger content. Keep ordinary
  `information_accessed` receipts content-blind; the growth source may retain only its proposal record ID
  because explicit adoption depends on proof of exact inspection.
  The reading window closes after exactly one read. The final model call may act, continue privately, or wait,
  but cannot request a second source. Immediate embodied observation remains outside this elective-read limit.
- Federation route discovery is an elective city source. Reading possible routes must not move a resident;
  actual city-to-city travel belongs to the resident host and must use the engine's recoverable departure
  and arrival contract before switching its WorldWeaver client.
- Inter-shard travel is ledger-recoverable. Once the source session is retired, the resident must not run a
  city core until the destination session exists; a restart resumes the same travel ID. If departure fails
  while the source session is verifiably alive, abort the trip and let local life continue.
- Information providers return structured records retaining provenance, freshness, locality, visibility,
  and selection mode. Render records only at the inference boundary; traces keep the structured form.
- Images and rendered PDF pages may accompany only the typed read that requested them and only under an
  explicit vision grant. Old-core prompt traces store their hashes and sizes, not the image bodies.
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
