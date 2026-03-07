# Scene Card as Universal Narrator Input

## Metadata

- ID: 113-scene-card-universal-narrator
- Type: major
- Owner: agent
- Status: backlog
- Risk: medium
- Target Window: v4 lane
- Depends On: Major 112 (unified intent pipeline)

## Problem

Narration quality and structure depends on which pipeline path produced the turn. The three current
paths generate prose in different ways:

| Path | Narration input |
|------|----------------|
| Freeform `/action` | `SceneCardOut` + intent text → scene narrator |
| JIT beat (choice turn) | raw state vars + ad-hoc prompt → narrator |
| Direct `set` fallback | raw state vars + minimal context → narrator |

Consequences:
- Narration richness varies by input type. `immediate_stakes`, `active_goal`, and `constraints`
  fields in `SceneCardOut` are computed but not consistently used on all paths.
- Adding narrator improvements (richer stakes, goal threading, motif callbacks) requires touching
  multiple code paths separately.
- The scene card is already the right abstraction — it is a structured intermediate representation
  of "what the player should experience right now." It just isn't used universally.

The vision calls for a single unified renderer: **scene card in → rich prose + choices out**.
Every turn, regardless of how it was triggered, should build a `SceneCardOut` from committed state
and pass it to one canonical scene narrator function.

## Proposed Solution

After every reducer commit — whether triggered by a freeform action, a choice button selection,
or a JIT beat — build a fresh `SceneCardOut` from the committed state and pass it to a single
`narrate_scene(card: SceneCardOut) -> NarrationResult` function. This function is the only
narrator entry point; all other per-path narration code is removed or consolidated into it.

### Scene Card Extensions

Extend `SceneCardOut` with two new optional fields that carry turn-specific context the narrator
needs but the state does not hold:

- `recent_action_summary: str | None` — one sentence: what the player just did (from the
  committed intent text). Gives the narrator a causal anchor ("having just descended the stairs,
  you find...").
- `available_choices: list[ChoiceOut] | None` — the next-turn choices, already generated.
  Including them in the card lets the narrator produce prose that sets up the choices naturally.

These fields do not change the game state schema; they are populated transiently during narration
and discarded.

### Narrator Consolidation

The shared `narrate_scene` function receives the full `SceneCardOut` and is responsible for:

1. Composing the narrator LLM prompt from the card's structured fields.
2. Generating the scene prose (can be long — the card contains all necessary context).
3. Returning a `NarrationResult` with prose text + any scene-level metadata.

Callers (action path, choice path, JIT beat path) call `narrate_scene` and do not compose
narrator prompts themselves.

## Files Affected

- `src/core/scene_card.py` — add `recent_action_summary` and `available_choices` to `SceneCardOut`;
  update builder functions
- `src/services/turn_service.py` — enforce scene card build after every reducer commit; route all
  narration calls through shared `narrate_scene`; remove per-path ad-hoc narrator prompt construction
- `src/api/game/action.py` — remove ad-hoc narration prompt; call shared `narrate_scene`
- `src/services/narrator.py` (new or existing) — canonical `narrate_scene` function

## Non-Goals

- Do not change the game state schema or reducer.
- Do not change the API response envelope (narration prose is still returned in the same fields).
- Do not change the storylet selection or JIT beat generation logic.
- Scene card is internal — no API contract changes needed.
- Do not pursue narrator quality improvements in this item; focus is consolidation only.

## Acceptance Criteria

- [ ] All three turn paths (JIT beat, freeform action, choice selection) call a single
      `narrate_scene` function that takes a `SceneCardOut`.
- [ ] `SceneCardOut` includes `recent_action_summary` and `available_choices` fields, populated
      on every turn where they are available.
- [ ] No per-path ad-hoc narrator prompt construction remains in `turn_service.py` or `action.py`.
- [ ] Narration quality on the JIT beat path is at least equivalent to the current freeform
      action path (qualitative check via playtest run review).
- [ ] `python scripts/dev.py quality-strict` passes.
- [ ] All existing tests pass.

## Validation Commands

- `python scripts/dev.py quality-strict`
- `python scripts/dev.py test`
- `python playtest_harness/llm_playtest.py --turns 20 --mom-mode`
- Read turn-by-turn narrative output across all pipeline modes; confirm consistent prose quality.

## Pruning Prevention Controls

- Authoritative path for touched behavior: `src/services/narrator.py` (new canonical narrator),
  `src/core/scene_card.py`, `src/services/turn_service.py`
- Parallel path introduced: none; consolidation removes existing parallel paths
- Optional/harness behavior on default path: no — scene card narration is the new single default
- Generated artifacts + archive target: none
- Flag lifecycle: none

## Risks and Rollback

Risks:

- JIT beat narration quality may temporarily regress during consolidation if the old ad-hoc
  prompt contained path-specific context that is not yet captured in the scene card.
  Mitigation: run parallel quality comparison before deleting old path; add missing context to
  `SceneCardOut` extensions.
- `available_choices` in the scene card creates a mild circular dependency (choices feed into
  narration that introduces choices). Mitigation: choices are generated first, passed in as
  read-only context — no mutation loop.

Rollback:

- Revert `narrate_scene` call sites to their previous per-path implementations.
- Remove `recent_action_summary` and `available_choices` from `SceneCardOut` (schema-additive,
  so removal is safe).
- No DB or state schema changes to undo.

## Follow-up Candidates

- Expose `SceneCardOut` snapshot in turn diagnostics for playtest analysis.
- Long scene narration mode: when `SceneCardOut` is rich, allow narrator to produce multi-paragraph
  immersive prose (configurable length target).
- Client rendering: pass `SceneCardOut` fields directly to client for structured UI rendering
  (stakes bar, goal thread, cast list) rather than embedding everything in prose.
