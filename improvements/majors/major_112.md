# Route Choice Selections Through the Unified Intent Pipeline

## Metadata

- ID: 112-unify-choice-intent-pipeline
- Type: major
- Owner: agent
- Status: backlog
- Risk: medium
- Target Window: v4 lane
- Depends On: Minor 119 (choice `intent` field)

## Problem

When a player clicks a choice button, `turn_service.py` applies the choice's `set` block directly
as `ActionDeltaSetOperation` — a raw vars mutation that bypasses all semantic understanding:

- No intent extraction: the system does not understand *what* the player intended to do.
- No validation: there is no check whether the action is plausible given world state.
- No causal narration: the narrative response is generated from the post-mutation state, losing
  the thread of "player did X → world responded Y."
- No reducer canonicalization for semantic fields like `location`: if `set` says
  `{location: "library"}` it writes `library` verbatim, not the canonical `library_archive`.

This is the root of two observable failures:
1. Choice-driven location changes can write non-canonical names if the JIT beat narrator
   generated a label with a non-canonical name in its `set` block.
2. Turn diagnostics (`pipeline_mode`) report `jit_beat` even when the player made a meaningful
   choice, obscuring which pipeline handled the turn.

The freeform `/action` path already has a correct 3-stage pipeline (intent extraction → ack →
validation → narration → reducer commit). Choice selections must route through the same pipeline
so that both input modalities are treated as first-class player intents.

## Proposed Solution

Route choice button selections through the same 3-stage intent pipeline currently used for
freeform actions, using the choice's `intent` field (Minor 119) as the semantic text input:

**Stage A — Intent + Ack**
Extract a `ChoiceSelectedIntent` from the choice's `intent` text and `set` block hints. Generate
a brief ack (1–2 sentences) confirming what the player committed to do. This is returned to the
client quickly as `phase:ack` — same streaming contract as freeform actions.

**Stage B — Validation**
Validate the extracted intent against current world state. Are there blockers? Is the location
reachable? If blocked, generate a constraint-respecting alternative outcome (e.g., "the door is
locked — you linger at the threshold instead"). This matches the existing freeform validation
gate in Stage B.

**Stage C — Commit + Narration**
Commit the validated intent delta to the reducer (not the raw `set` block). The reducer applies
its canonical normalization, clamp policies, and blocked-key rules as usual. Build a `SceneCardOut`
from the committed state. Pass the scene card to the scene narrator to generate the full
consequence prose. Emit `phase:commit` and `phase:narrate` events.

The `set` block values are *outcome hints* passed alongside the extracted intent — they inform the
reducer about expected state changes but do not bypass it. Reducer remains the sole authority.

**Fallback**: If `intent` field is absent (pre-Minor-119 choices or LLM omission), fall back to
the existing direct `set` block application so no regression occurs.

**Diagnostics**: `pipeline_mode` in turn record becomes `unified_intent` for all choice turns
processed through the new path (vs. `jit_beat` for the fallback path).

### Shared Pipeline Extraction

The 3-stage pipeline logic currently embedded in `src/api/game/action.py` must be extracted into
shared functions callable from both the freeform action path and the new choice path:

```
src/services/intent_pipeline.py  (new module, extracted from action.py)
  ├── run_stage_a(intent_text, context) -> AckResult
  ├── run_stage_b(ack_result, world_state) -> ValidationResult
  └── run_stage_c(validation_result, scene_card) -> NarrationResult
```

Both `action.py` and the choice handler call into these shared functions. No duplication.

## Files Affected

- `src/api/game/action.py` — extract pipeline stages into shared module; update to call shared functions
- `src/services/intent_pipeline.py` — new module; extracted 3-stage pipeline logic
- `src/services/turn_service.py` — choice handling branch; route through `intent_pipeline` when `intent` present
- `src/api/game/next.py` (or equivalent) — thread choice `intent` field into turn service call
- `src/services/rules/schema.py` — `ChoiceSelectedIntent` may need extension for hint-vs-command distinction

## Non-Goals

- Do not change the JIT beat *generation* logic or its output format.
- Do not change the freeform `/action` path behaviour — extraction only, no functional change there.
- Do not add streaming to the choice response yet if it requires significant new infrastructure.
- Do not change the reducer contract or blocked-key policy.
- Do not remove the `set` block fallback until Minor 119 has been shipped and verified.

## Acceptance Criteria

- [ ] A choice button click with an `intent` field produces a turn record with
      `pipeline_mode = unified_intent` in diagnostics.
- [ ] State mutations from choice buttons pass through reducer canonical normalization —
      no raw `ActionDeltaSetOperation` bypass on the unified path.
- [ ] Location changes via choice buttons write canonical location slugs (same guarantee as
      the freeform path after Minor 118).
- [ ] `active_storylets_count` is evaluated after the full pipeline commit, not before.
- [ ] Choices with no `intent` field fall back to the existing direct `set` path without error.
- [ ] Freeform `/action` path behaviour is unchanged (extract-only refactor for `action.py`).
- [ ] `python scripts/dev.py quality-strict` passes.
- [ ] All existing tests pass (no regression on 800+ test suite).

## Validation Commands

- `python scripts/dev.py quality-strict`
- `python scripts/dev.py test`
- `python playtest_harness/llm_playtest.py --turns 20 --mom-mode`
- `python playtests/state_arc.py playtests/agent_runs/<run_id>`
  - Confirm `pipeline_mode = unified_intent` for choice turns in diagnostics output.
  - Confirm location names in state arc are canonical for choice-driven transitions.

## Pruning Prevention Controls

- Authoritative path for touched behavior: `src/services/intent_pipeline.py` (new, extracted),
  `src/api/game/action.py`, `src/services/turn_service.py`
- Parallel path introduced: `intent_pipeline.py` is an extraction of existing `action.py` logic —
  expiry condition: once both callers use it, old inline code in `action.py` is deleted (same PR).
- Optional/harness behavior on default path: no — `intent_pipeline` is the new default path for
  both input modalities.
- Generated artifacts + archive target: none
- Flag lifecycle: none (fallback to `set` path is conditional on `intent` field presence, not a flag)

## Risks and Rollback

Risks:

- Pipeline adds latency to choice responses. The 3-stage LLM chain takes time. Mitigation: Stage A
  ack is returned quickly; B and C can be parallelized or streamed. Profile before optimizing.
- `set` block values conflict with pipeline validation (e.g., `set` says location X but validation
  blocks it). Mitigation: treat `set` as hints, not commands; validation outcome is authoritative.
- Extracted `intent_pipeline.py` module introduces a new import boundary. Mitigation: keep module
  thin — only orchestration, no new LLM clients or config.

Rollback:

- Remove `intent_pipeline.py` import from `turn_service.py` choice branch; restore direct
  `ActionDeltaSetOperation` application. No DB schema changes, no state format changes.

## Follow-up Candidates

- Major 113: Scene card as universal narrator input (completes the pipeline vision)
- Stream choice responses with `phase:ack` → `phase:commit` → `phase:narrate` envelope (same as freeform)
- Expose `pipeline_mode` in the client UI for developer debug overlay
