# Split freeform action resolution into intent → validate → narrate (streamed) pipeline

## Problem
Freeform actions are currently expensive because one LLM pass often does too much:
- interpret intent,
- decide world/state changes,
- generate narration,
- propose choices,
- and sometimes infer goal updates.

This increases latency and makes it harder to provide immediate feedback while preserving deterministic safety.

## Proposed Solution
Implement a two-stage (optionally three-stage) action pipeline that is streaming-friendly and validator-first.

1. Stage A: Intent + delta proposal (small, fast)
   - LLM returns structured JSON only:
     - `ActionDeltaContract` operations (set/increment/append_fact),
     - optional `goal_update`,
     - optional `suggested_beats`,
     - a short `ack_line` (1 sentence) for immediate player feedback.
   - Keep the prompt short and tightly constrained.

2. Deterministic validation + commit
   - Apply the delta contract through the deterministic validator.
   - Record world events/facts as usual.
   - Reject/clip invalid operations with a clear contradiction note stored in metadata.

3. Stage B: Narration render (streamed, can be slower)
   - LLM receives:
     - validated state changes (not the raw proposal),
     - current scene stub (if available),
     - a small fact pack (relevant world facts).
   - Output is narration only + 2–6 follow-up choice suggestions.
   - Stream output via SSE with explicit phase events:
     - `phase:ack`, `phase:commit`, `phase:narrate`.

4. Fallback path
   - If Stage A fails or times out, fall back to the current single-pass action endpoint behavior.

## Files Affected
- `src/services/command_interpreter.py` (refactor into stage A + stage B)
- `src/services/llm_service.py` (new structured "intent" prompt + response validation)
- `src/api/game/action.py` (SSE phases and fallback logic)
- `src/models/schemas.py` (optional: add `ack_line` to ActionResponse; keep backward compatibility)
- `tests/api/test_action_endpoint.py` (add coverage for staged flow + fallback)
- `tests/service/test_command_interpreter.py` (new)

## Acceptance Criteria
- [ ] `/api/action/stream` streams an immediate ack line within ~2 seconds for typical actions (local dev with real API key).
- [ ] All state changes are applied only after deterministic validation; invalid ops are rejected and logged in metadata.
- [ ] Narration generation uses only validated state changes and does not mutate state directly.
- [ ] Fallback to the existing single-pass path works if Stage A fails.
- [ ] No existing client integration breaks (ActionResponse remains compatible).
- [ ] `pytest -q` passes.

## Risks & Rollback
Splitting action into phases adds complexity and more moving parts. Mitigate with strict schema validation and a reliable fallback. Roll back by disabling staged mode with a feature flag and returning to the current single-pass behavior.
