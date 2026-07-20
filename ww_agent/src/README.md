# Source map

- `main.py` — process entry point, configuration, resident discovery, shared clients, and task startup.
- `resident.py` — shared resident host and lifecycle: one home, one core, and one exclusive city or hearth
  attachment. It owns mirror quiescence, confirmed city departure, core rebuild, fresh city return,
  keeper-whisper wake signals, and optional tick-count or elapsed-time bounds and read-only observers used
  by operational surfaces. A time-bound host run changes no cognitive clock; the core keeps its own cadence.
- `runtime/cognitive_core.py` — authoritative perceive → integrate → ignite → pulse → act path.
- `runtime/ledger.py` — append-only event history and a versioned current-state checkpoint. Major 137 is
  repairing bounded replay that can lose older open work, silent malformed-record handling, dead projection
  files, and remaining full-history readers. It also derives the small relationship view from prompt-delivery
  and reply edges; `mirror.py` exposes that derived runtime state.
- `runtime/prompt_trace.py` — private inference-boundary evidence, excluded from all substrate reducers.
- `runtime/prompt_context.py` — typed available/selected/withheld source envelope and final prose renderer.
- `runtime/information.py` — private elective source access plus the structured provider-record contract;
  separate from outward effectors. It briefly reuses an equivalent successful read so repeated requests do
  not reopen the same source or trigger another continuation model call.
- `runtime/perception.py` — assigns source identity, emits encounters once, and renders still-pending
  speech and physical-trace encounters for prompts; `cognitive_core.py` marks prompt-included packets
  observed.
- `runtime/integrator.py`, `salience.py`, `prediction.py` — turn world changes into pressure and candidate
  action.
- `runtime/pulse.py`, `pulse_engine.py`, `effectors.py` — form a pulse, distinguish private `reach` from
  outward `act`, and discharge only the latter through concrete effectors. The bounded reach continuation
  closes its source catalog on the last allowed read and cannot route an unfulfillable extra request. The
  resident host owns the limit (two by default), while the integrator records content-blind cost and timing.
- `runtime/travel.py` — classifies world travel separately from ordinary movement and derives unfinished
  city handoffs from ledger evidence; worlds signal intent and `resident.py` performs or resumes the
  lifecycle change without running cognition between nodes.
- `runtime/memory.py`, `drive.py`, `anchors.py`, `incubation.py`, `circadian.py` — supporting substrate
  state. These are modules inside the unified runtime, not independent schedulers.
- `identity/growth.py`, `runtime/workshop.py`, `runtime/doula.py` — resident-controlled identity growth,
  private making, and optional birth support. Growth proposals remain private and change identity only
  after the resident inspects and explicitly adopts one at their hearth. Workshop entries use
  machine-written ISO timestamp boundaries; Markdown headings
  inside a resident's prose remain part of that entry. The doula records each birth in the new resident's
  ledger and shared process settings in its separate administrative ledger before the resident boots.
  A fixed steward-requested batch can instead stop with a hearth manifest in the dormant state; it does
  not enter the daemon's spawn queue.
- `world/client.py` — async WorldWeaver HTTP client, including the engine's recoverable inter-shard travel
  calls; `city_world.py` and `city_tools.py` adapt the named city source registry to runtime protocols.
  Possible routes and live nodes are available through the elective `travel` source, not ambient scene
  narration. On game shards, objects, making, stoops, accepted exchange, and exact-place access are likewise
  elective reads; any resulting custody or door change uses a typed effector and canonical engine receipt.
  Sources enter perception as typed affordances, never fake events; physical `mark` acts use the separate
  local trace endpoint. Unknown physical prose is declined locally rather than sent to `/api/action`.
- `inference/client.py` — OpenAI-compatible completion boundary.
- `identity/loader.py` — resident identity, tuning compatibility, and factual situational briefing.
  `identity/README.md` defines the separation among durable identity, the resident's hearth shard, current
  world attachment, and the computer temporarily hosting the runtime; `identity/hearth_manifest.py`
  provides the first portable-hearth identity contract, and `identity/hearth_package.py` inventories what
  can move without copying city state or host credentials. `identity/hearth_activation.py` holds one local
  runtime lock and makes an orderly imported successor advance while its stopped source retires.
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
