# Replace heuristic graph fact extraction with structured world-fact channel

## Problem
Knowledge-graph extraction currently depends heavily on heuristic text parsing, which is brittle under varied LLM phrasing and can silently create duplicates, malformed facts, or missed updates over long playthroughs.

## Proposed Solution
Promote graph-fact ingestion to a schema-first pathway with explicit fallback handling.

1. Define strict world-fact extraction schemas and validators (entity identity, predicate, confidence, provenance).
2. Update planner/narrator prompting to emit schema-valid fact payloads via structured JSON output.
3. Route world-memory ingestion through a typed parser first, with heuristic parsing retained only as an explicit fallback path.
4. Add canonical entity normalization and duplicate suppression before persistence.
5. Persist extraction provenance (`source`, `parser_mode`, `fallback_reason`) for auditability and replay/debug.

## Files Affected
- `src/services/world_memory.py`
- `src/services/llm_service.py`
- `src/services/prompt_library.py`
- `src/models/schemas.py`
- `src/services/runtime_metrics.py`
- `tests/service/test_world_memory.py`
- `tests/service/test_llm_service.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria
- [ ] Primary fact extraction path is schema-validated and rejects malformed payloads safely.
- [ ] Heuristic extraction is fallback-only and records explicit fallback reasons.
- [ ] Duplicate entity/fact creation is reduced via canonical identity normalization.
- [ ] World-memory ingest remains route-compatible and non-breaking for callers.
- [ ] Regression tests cover malformed/partial/variant LLM outputs.

## Validation Commands
- `pytest -q tests/service/test_world_memory.py tests/service/test_llm_service.py`
- `pytest -q tests/api/test_game_endpoints.py`
- `python scripts/dev.py quality-strict`

## Risks & Rollback
- Risk: strict validation may drop useful facts when model output is partially malformed.
- Risk: schema migration can temporarily reduce graph richness if prompts are not tuned.
- Rollback: keep heuristic extraction as a feature-flagged fallback default while structured output is tuned and stabilized.
