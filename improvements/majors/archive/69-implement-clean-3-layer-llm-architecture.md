# Implement clean 3-layer LLM architecture (Referee -> Reducer -> Narrator)

## Problem

The runtime already contains pieces of a staged pipeline (`intent -> validate ->
narrate`), an authoritative reducer, and scene-card generation. But these
capabilities are not yet enforced as one strict architecture boundary across
all action-turn paths.

Current gaps:

1. LLM planning and LLM narration concerns are still partially mixed in
   interpreter pathways.
2. The reducer is authoritative, but growth controls are not consistently
   enforced as a first-class "state cannot grow without bound" policy.
3. Scene cards are generated on demand but not persisted as the canonical "Now"
   turn object used for replay/debug and prompt discipline.
4. Narration constraints ("cannot invent state deltas") exist by convention but
   need stronger contract enforcement and tests.

This produces avoidable randomness and continuity drift under long runs.

## Proposed Solution

Harden and unify the runtime into a strict 3-layer architecture:

1. Referee / Planner (LLM, structured, slow-ish):
   - Input: persisted Scene Card + relevant fact pack + recent event summary.
   - Output: compact delta contract + rationale + confidence + trigger hints.
   - No prose generation in this layer.
2. Reducer (deterministic, no model):
   - Sole authority for applying all state deltas.
   - Enforces clamps, mutual exclusion, aliases, TTL decay, and bounded-growth
     limits for unstructured/state-bag and fact accumulation.
   - Commits event/fact/projection artifacts from reducer receipts.
3. Narrator (LLM, fast, creative):
   - Input: Scene Card + committed reducer deltas + small fact pack.
   - Output: prose + follow-up choices only.
   - Any attempted state mutation fields are ignored and logged.

Implementation slices:

1. Extract explicit planner/narrator boundaries from interpreter services and
   route through one orchestration path in turn service.
2. Persist a canonical turn Scene Card ("Now") each turn with:
   - `location`, `sublocation`
   - `cast_on_stage`
   - `immediate_stakes`
   - `constraints_or_affordances`
   - `active_goal`, `goal_urgency`, `goal_complication`
3. Add bounded-growth rulebook policies to reducer/state lifecycle:
   - hard caps and TTL decay for unstructured state bags
   - bounded fact/event prompt-pack inputs
   - pruning/normalization receipts for auditability
4. Add strict tests proving:
   - narrator cannot mutate state
   - only reducer-committed deltas become authoritative
   - scene card persistence/replay works per turn
5. Keep external route/path/payload contracts stable.

## Files Affected

- `src/services/turn_service.py`
- `src/services/command_interpreter.py`
- `src/services/action_validation_policy.py`
- `src/services/rules/reducer.py`
- `src/services/rules/schema.py`
- `src/services/state_manager.py`
- `src/services/world_memory.py`
- `src/core/scene_card.py`
- `tests/api/test_action_endpoint.py`
- `tests/service/test_turn_service.py`
- `tests/service/test_reducer.py`
- `tests/service/test_world_memory.py`
- `improvements/ROADMAP.md`

## Acceptance Criteria

- [x] Freeform action runtime executes strict sequence:
      Planner proposal -> Reducer commit -> Narrator prose.
- [x] Planner output is contract-only (delta/rationale/confidence) and contains
      no narrative text payload dependency.
- [x] Narrator receives committed deltas and cannot introduce net-new
      authoritative state changes.
- [x] Reducer enforces bounded-growth policy (caps + decay) and records
      normalization/pruning evidence in receipts or event metadata.
- [x] Canonical Scene Card "Now" object is persisted each turn and used as
      primary LLM context input instead of full sprawling state dumps.
- [x] Action replay/idempotency remains correct with the 3-layer pipeline.
- [x] No API route/path/payload contract changes are introduced.
- [x] `python -m pytest -q` passes.
- [x] `npm --prefix client run build` passes.

## Risks & Rollback

Risks:

1. Over-constraining planner/narrator contracts can reduce narrative quality.
2. Aggressive growth caps can prematurely drop context if thresholds are too
   tight.
3. Scene-card persistence bugs can cause stale turn context.

Rollback:

1. Keep an explicit feature flag for strict 3-layer enforcement.
2. Fall back to current staged interpreter path if strict mode regresses.
3. Revert this major's commits and retain reducer/state safety fixes that are
   independently verified.
