# Source map

- `main.py` — process entry point, configuration, resident discovery, shared clients, and task startup.
- `resident.py` — shared resident host and lifecycle: one home, one core, and one exclusive city or hearth
  attachment. It owns mirror quiescence, confirmed city departure, core rebuild, fresh city return,
  keeper-whisper wake signals, and optional read-only tick observers used by operational surfaces.
- `runtime/cognitive_core.py` — authoritative perceive → integrate → ignite → pulse → act path.
- `runtime/ledger.py` — durable append-only evidence, bounded working-history reads, and a versioned
  current-state checkpoint. It also derives the small relationship view from prompt-delivery and reply
  edges; `mirror.py` exposes that derived runtime state.
- `runtime/prompt_trace.py` — private inference-boundary evidence, excluded from all substrate reducers.
- `runtime/prompt_context.py` — typed available/selected/withheld source envelope and final prose renderer.
- `runtime/information.py` — private elective source access plus the structured provider-record contract;
  separate from outward effectors.
- `runtime/perception.py` — assigns source identity, emits encounters once, and renders still-pending
  speech and physical-trace encounters for prompts; `cognitive_core.py` marks prompt-included packets
  observed.
- `runtime/integrator.py`, `salience.py`, `prediction.py` — turn world changes into pressure and candidate
  action.
- `runtime/pulse.py`, `pulse_engine.py`, `effectors.py` — form a pulse, distinguish private `reach` from
  outward `act`, and discharge only the latter through concrete effectors.
- `runtime/travel.py` — classifies world travel separately from ordinary movement; worlds signal intent
  and `resident.py` performs the lifecycle change.
- `runtime/memory.py`, `drive.py`, `anchors.py`, `incubation.py`, `circadian.py` — supporting substrate
  state. These are modules inside the unified runtime, not independent schedulers.
- `runtime/growth_proposals.py`, `workshop.py`, `doula.py` — identity growth, private making, and optional
  birth/proposal support. The doula records each birth in the new resident's ledger and shared process
  settings in its separate administrative ledger before the resident boots.
- `world/client.py` — async WorldWeaver HTTP client; `city_world.py` and `city_tools.py` adapt the named city
  source registry to runtime protocols. Sources enter perception as typed affordances, never fake events;
  physical `mark` acts use the separate local trace endpoint.
- `inference/client.py` — OpenAI-compatible completion boundary.
- `identity/loader.py` — resident identity, tuning compatibility, and factual situational briefing.
- `familiar/` — the private hearth adapter and its optional grants. `config.py` reads per-resident
  `hearth.json`; `file_scope.py` enforces read roots, ignore rules, secret denial, bounded pagination,
  path recovery, and bounded image/PDF reads; `visual.py` converts an explicitly requested visual file
  into text and optional image blocks; `weather.py` is enabled only when configured. A normal resident enters the hearth
  without an invented keeper, FileScope, weather lookup, host tool, or network grant.

The deleted `loops/` and tiered `memory/` packages are historical architecture. New behavior belongs in
the unified runtime unless an active work item explicitly changes that ownership.
