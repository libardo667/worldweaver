# Harmonize storylet generation validation constraints

## Problem
The `WorldDescription` Pydantic schema currently strictly enforces `storylet_count: int = Field(ge=5, le=50)`. While this makes sense for the classic "batch generation" pipeline (which needs to populate a 15-storylet graph), it causes silent, catastrophic `ValidationErrors` when reused by the JIT (Just-In-Time) pipeline, which legitimately only ever needs a `storylet_count=1` to generate an isolated starting beat or responsive action.

## Proposed Solution
Decouple or harmonize the validation rules to support both architectural pipelines seamlessly:
1. **Schema Inheritance:** Break `WorldDescription` into a `BaseWorldContext` (containing theme, tone, descriptions) and two specialized subclasses: `BatchGenerationRequest` (enforcing `ge=5`) and `JITGenerationRequest` (enforcing `eq=1`).
2. **Service Refactor:** Update `world_bootstrap_service.py` and `llm_service.py` to accept the appropriate, correctly-constrained schema based on the active feature flags.
3. **Audit Assertions:** Audit other shared schemas (like `Choice`, `Storylet`) to ensure no other hardcoded invariants implicitly assume a batch-generation context.

## Files Affected
- `src/models/schemas.py` (Refactor `WorldDescription` and subclasses)
- `src/services/llm_service.py` (Update generation signatures to accept base context or specialized payloads)
- `src/services/world_bootstrap_service.py` (Supply the correct payload subclass based on JIT/Batch flag)
- `src/api/game/story.py` (Review endpoint validation logic)

## Acceptance Criteria
- [ ] JIT bootstrap safely generates a single starting storylet without throwing a `ValidationError` workaround or hacking `storylet_count=5`.
- [ ] The classic batch generation path still enforces a minimum of 5 storylets to ensure graph viability.
- [ ] All `pytest` models validating the API shapes pass without throwing coercion warnings.

## Risks & Rollback
**Risk:** Refactoring `WorldDescription` may break frontend endpoints or clients that rigidly expect a unified `WorldDescription` object for all world-generation requests.
**Mitigation:** Expose a unified facade endpoint that accepts a loose payload, validates it via a union `WorldDescription = Union[BatchGenerationRequest, JITGenerationRequest]`, and dynamically dispatches to the correct pipeline.
**Rollback:** Revert schema split and restore the hardcoded `ge=5` with the `count=5` workaround.
