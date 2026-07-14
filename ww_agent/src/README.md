# Source map

- `main.py` — process entry point, configuration, resident discovery, shared clients, and task startup.
- `resident.py` — per-resident composition root and lifecycle.
- `runtime/cognitive_core.py` — authoritative perceive → integrate → ignite → pulse → act path.
- `runtime/ledger.py` — durable append-only evidence; `mirror.py` exposes derived runtime state.
- `runtime/prompt_trace.py` — private inference-boundary evidence, excluded from all substrate reducers.
- `runtime/perception.py` — assigns source identity, emits encounters once, and renders still-pending
  encounters for prompts; `cognitive_core.py` marks prompt-included packets observed.
- `runtime/integrator.py`, `salience.py`, `prediction.py` — turn world changes into pressure and candidate
  action.
- `runtime/pulse.py`, `pulse_engine.py`, `effectors.py` — form a pulse and discharge it through concrete
  capabilities.
- `runtime/memory.py`, `drive.py`, `anchors.py`, `incubation.py`, `circadian.py` — supporting substrate
  state. These are modules inside the unified runtime, not independent schedulers.
- `runtime/growth_proposals.py`, `workshop.py`, `doula.py` — identity growth, private making, and optional
  birth/proposal support.
- `world/client.py` — async WorldWeaver HTTP client; `city_world.py` and `city_tools.py` adapt city
  affordances to runtime protocols.
- `inference/client.py` — OpenAI-compatible completion boundary.
- `identity/loader.py` — resident identity, tuning compatibility, and factual situational briefing.
- `familiar/` — explicitly scoped local file, weather, and local-world tools.

The deleted `loops/` and tiered `memory/` packages are historical architecture. New behavior belongs in
the unified runtime unless an active work item explicitly changes that ownership.
