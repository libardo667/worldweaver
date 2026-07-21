# Source map

- `main.py` — process entry point, configuration, resident discovery, shared clients, and task startup.
- `resident.py` — shared resident host and lifecycle: one home, one reference core, and one exclusive city or
  hearth attachment. It owns confirmed city departure, core rebuild, fresh city return, durable city-signal
  waiting and session-bound cursor restoration, keeper-whisper wake signals, optional tick-count or elapsed-time
  bounds, and read-only observers used by operational surfaces. A time-bound host run changes no cognitive
  clock; the core keeps its own cadence.
- `runtime/reference_core.py` — production resident loop. It observes current-place facts, accepts a
  cursor-delivered local-speech batch without fetching it again, activates on a new local signal or slow
  baseline, permits one elective read, and accepts one final action, private continuation, or wait choice. A
  rebuilt core loads a bounded typed view of its own recently confirmed actions from the private checkpoint;
  it does not restore prompts, completions, or action prose.
- `runtime/process_state.py` — small versioned resident-process fields that can be shared by the reference
  adapter and later model adapters. It currently defines confirmed-action receipts and their exact renderer.
- `runtime/cognitive_core.py` — audited predecessor. It is not constructed by the resident host; keep it only
  as comparison and selective migration material until its remaining useful contracts are separated.
- `runtime/ledger.py` — append-only event history and a versioned current-state checkpoint. Major 137 is
  classifying remaining full-history readers. New events use
  a serialized, durably flushed sequence; an incomplete final write is quarantined and completed-record
  corruption stops replay. Open routes, mail, research, packets, and intents advance from the checkpoint and
  cannot be evicted by bounded recent history. Replay clocks are explicit, and queue expiry produces a named
  terminal event. Normal append writes no standalone projection or snapshot shadows. It also derives the
  small relationship view from prompt-delivery and reply edges. These private projections stay in the hearth
  and are not copied into city session storage. Its runtime projection keeps no more than twelve versioned
  confirmed-action receipts so a restart can recover exact bookkeeping without replaying or summarizing a
  resident's life.
- `runtime/prompt_trace.py` — legacy-core diagnostic code; it is not wired into the production reference loop.
- `runtime/prompt_context.py` — typed available/selected/withheld source envelope and final prose renderer.
- `runtime/information.py` — private elective source access plus the structured provider-record contract;
  separate from outward effectors. It briefly reuses an equivalent successful read so repeated requests do
  not reopen the same source or trigger another continuation model call. Durable access receipts omit the
  query, returned prose, and ordinary record IDs; identity growth retains only the proposal ID required for
  explicit adoption.
- `runtime/perception.py`, `integrator.py`, `salience.py`, `prediction.py`, and `pulse_engine.py` — old-core
  mechanisms retained for tests and individual review; they are not the production scheduler.
- `runtime/pulse.py` — currently supplies the typed read/action data contracts used at the narrow adapter.
- `runtime/effectors.py` — sends final typed action attempts to concrete world rules.
- `runtime/travel.py` — classifies world travel separately from ordinary movement and derives unfinished
  city handoffs from ledger evidence; worlds signal intent and `resident.py` performs or resumes the
  lifecycle change without running cognition between nodes.
- `runtime/memory.py`, `drive.py`, `anchors.py`, `incubation.py`, `circadian.py` — supporting substrate
  state. These are modules inside the unified runtime, not independent schedulers.
- `identity/growth.py`, `identity/resident_creation.py`, `runtime/workshop.py`, `runtime/doula.py` —
  resident-controlled identity growth, plain steward-created resident homes, private making, and legacy
  model-written birth support. Growth proposals remain private and change identity only
  after the resident inspects and explicitly adopts one at their hearth. Workshop entries use
  machine-written ISO timestamp boundaries; Markdown headings
  inside a resident's prose remain part of that entry. The normal creation path writes only a chosen name,
  structural hearth identity, and a host-sealed signing key, leaving the ledger empty and the hearth dormant.
  The old Doula remains comparison and migration code; its model-written batch apply command is disabled.
- `world/client.py` — async WorldWeaver HTTP client, including durable exact-place signal cursors and exact
  request signing for an injected resident runtime certificate and the engine's recoverable inter-shard travel
  calls; `city_world.py` and `city_tools.py` adapt the named city source registry to runtime protocols.
  Possible routes and live nodes are available through the elective `travel` source, not ambient scene
  narration. On game shards, objects, making, stoops, accepted exchange, and exact-place access are likewise
  elective reads; any resulting custody or door change uses a typed effector and canonical engine receipt.
  Sources enter perception as typed affordances, never fake events; physical `mark` acts use the separate
  local trace endpoint. Unknown physical prose is declined locally rather than sent to `/api/action`.
  `world/resident_signing.py` signs transport bytes only; it does not issue certificates or load live keys.
- `inference/client.py` — OpenAI-compatible completion boundary.
- `identity/loader.py` — resident identity, portable display name, tuning compatibility, and factual
  situational briefing.
  `identity/README.md` defines the separation among durable identity, the resident's hearth shard, current
  world attachment, and the computer temporarily hosting the runtime; `identity/hearth_manifest.py`
  provides the first portable-hearth identity contract, and `identity/hearth_package.py` inventories what
  can move without copying city state or host credentials. `identity/hearth_activation.py` holds one local
  runtime lock and makes an orderly imported successor advance while its stopped source retires.
  `identity/hearth_envelope.py` provides authenticated encryption for one reviewed host. The package module
  can wrap and import its deterministic archive without writing a plaintext temporary ZIP. A folder-owned
  host key and reviewed resident identity card now support an operator import into a new dormant home; real
  resident signing-key custody, encrypted operator export, host authorization, and activation remain later
  steps. `identity/resident_identity.py` defines the portable, self-signed public identity card without
  treating that card as city admission or host ownership.
- `familiar/` — the private hearth adapter and its optional grants. `config.py` reads per-resident
  `hearth.json`; `file_scope.py` enforces read roots, ignore rules, secret denial, bounded pagination,
  path recovery, and bounded image/PDF reads; `visual.py` converts an explicitly requested visual file
  into text and optional image blocks; `local_world.py` exposes configured gifts as an elective private
  source rather than scene narration, including safe nested paths in a carried Stable inbox; `weather.py`
  is enabled only when configured. A normal resident enters the hearth without an invented keeper,
  FileScope, weather lookup, host tool, or network grant. Configured city names appear as adjacent nodes in
  the private scene graph, letting the shared movement/travel path carry an elective return to the city.

The deleted `loops/` and tiered `memory/` packages are historical architecture. New behavior belongs in
the unified runtime unless an active work item explicitly changes that ownership.
