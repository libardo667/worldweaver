# Orchestration Duplication And Fallback Map (Updated After Batch B Runtime API)

Status: `execution_updated`  
Scope: track duplicate patterns plus execution delta from Batch B runtime API slices.

## Resolved Endpoint-Layer Duplication (Batch B Runtime API)

### Trace id resolution helpers
- Prior pattern: duplicated `_active_trace_id` logic across `story.py`, `action.py`, `turn.py`.
- Resolution: centralized in `src/api/game/runtime_helpers.py` (`active_trace_id`).
- Evidence: `BATCH_B_RUNTIME_API_SLICE_1.md`.

### Request timing log envelopes
- Prior pattern: repeated route timing + structured request log + metrics reset wrappers.
- Resolution: centralized in `src/api/game/runtime_helpers.py` (`finalize_request_metrics`).
- Evidence: `BATCH_B_RUNTIME_API_SLICE_1.md`.

### Prefetch scheduling wrappers
- Prior pattern: repeated best-effort prefetch schedule + exception log + timing capture.
- Resolution: centralized in `src/api/game/runtime_helpers.py` (`schedule_prefetch_async_best_effort`, `schedule_prefetch_sync_best_effort`).
- Evidence: `BATCH_B_RUNTIME_API_SLICE_2.md`.

### Session lock and orchestrator delegation
- Prior pattern: each endpoint repeated lock + adapter argument wiring into `TurnOrchestrator`.
- Resolution: centralized in `src/api/game/orchestration_adapters.py` with endpoint seam preservation.
- Evidence: `BATCH_B_RUNTIME_API_SLICE_3.md`.

### Route-start boilerplate
- Prior pattern: repeated per-handler setup for route bind, response trace header, request start, timings dict.
- Resolution: centralized in `src/api/game/runtime_helpers.py` (`begin_route_runtime`).
- Evidence: `BATCH_B_RUNTIME_API_SLICE_4.md`.

### Semantic goal parsing duplication
- Prior pattern: endpoint-local semantic goal parser duplicate in `src/api/game/action.py`.
- Resolution: endpoint copy removed; canonical utility remains in `src/services/turn_service.py`.
- Evidence: `BATCH_B_RUNTIME_API_SLICE_1.md`.

## Remaining Optional Endpoint Candidate
- Route-local SSE/phase event shaping in `src/api/game/action.py` remains intentionally local due contract sensitivity (`/api/action/stream` event ordering and payload shape).

## Fallback Chains In Canonical Turn Orchestrator

### Action pipeline fallback chain
- `enable_strict_three_layer_architecture`
- `enable_staged_action_pipeline`
- staged `interpret_action_intent` path
- deterministic `interpret_action` fallback path

Observed chain:
1. try staged intent path
2. validate intent
3. fall back to deterministic interpreter when staged intent unavailable
4. strict mode can return deterministic acknowledgement payload

### Next-turn fallback chain
- JIT beat generation path when enabled
- fallback to storylet selection path on JIT failure
- idle fallback text when no eligible storylet selected
- template fallback when adaptation text is empty

Observed chain:
1. JIT beat path when enabled
2. on JIT failure, return to storylet selection path
3. if no storylet selected, emit engine-idle fallback text
4. if adaptation yields empty text, fall back to template render

## Pruning Implication
- Endpoint wrapper duplication is materially reduced.
- Next simplify leverage is now in `runtime_services` (feature-gated improvement flows and weak-reachability service hotspots), then `tests_integration` and `frontend_source`.
