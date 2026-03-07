# Add bootstrap seeding critical-path and prompt surface report

## Problem
Bootstrap behavior is hard to reason about during reviews because key decisions are spread across route handlers, bootstrap services, LLM service calls, and prompt builders. Teams currently have no single authoritative artifact that answers:

- what startup seeding uses as inputs,
- which LLM prompts/models are on the critical path,
- where deterministic fallbacks activate,
- and which parts affect first-turn readiness.

## Proposed Solution
Add an explicit bootstrap seeding report surface for engineering review and harness evidence.

1. Add a maintained documentation artifact that maps:
   - `/session/bootstrap` and startup orchestration call graph,
   - data seeded into session state before first turn,
   - prompt builders and model lanes used by bootstrap generation,
   - fallback paths and feature-flag gates.
2. Add additive diagnostics output for bootstrap/startup responses (or debug mode) that captures:
   - selected bootstrap mode (`jit` vs `classic`),
   - prompt/function path taken,
   - world-bible generation status and fallback status.
3. Add a lightweight test that enforces presence/shape of this diagnostics block when enabled.

## Files Affected
- `src/api/game/state.py`
- `src/services/world_bootstrap_service.py`
- `src/services/llm_service.py`
- `tests/api/test_game_endpoints.py`
- `improvements/harness/04-QUALITY_GATES.md`

## Acceptance Criteria
- [ ] A single maintained artifact documents the bootstrap critical path and prompt inventory.
- [ ] Bootstrap/startup diagnostics can expose which seeding path and fallback mode were used.
- [ ] Diagnostics are additive and do not break existing route contracts.
- [ ] Tests validate diagnostics presence/shape when the debug surface is enabled.

## Validation Commands
- `pytest -q tests/api/test_game_endpoints.py`
- `python scripts/dev.py quality-strict`

## Risks & Rollback
- Risk: diagnostics payload drift can occur if prompt paths evolve without doc updates.
- Rollback: keep docs artifact, disable runtime diagnostics emission behind flag/default-off.
