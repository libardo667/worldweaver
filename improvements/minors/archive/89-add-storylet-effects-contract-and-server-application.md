# Add a storylet effects contract and server-side application on fire/choice commit

## Problem

Storylets currently rely on `requires`/`choices` plus narration, but there is no
first-class `effects` contract that deterministically applies world/state changes
when a storylet fires or a choice commits.

## Proposed Solution

Add optional structured storylet effect operations:

1. Extend storylet schema with optional `effects` list (typed operations).
2. Apply effects through the server reducer when a storylet fires and/or when a
   selected choice commits.
3. Record applied effects in event metadata for replay/debug.

## Scope Boundaries

- Keep existing API routes and response envelopes stable.
- Keep effect application deterministic and server-authoritative (reducer-only writes).
- Additive contract only: storylets without `effects` must remain behaviorally unchanged.
- No prompt-only side effects; all effects must flow through typed reducer operations.

## Assumptions

- Storylet effects are represented as typed operations and can be translated to `ActionDeltaContract`.
- Fire-time effects should apply during `/next` storylet selection commit.
- Choice-commit effects should apply only when a client submits `choice_taken` on a later `/next` turn.

## Files Affected

- `src/models/__init__.py`
- `src/models/schemas.py`
- `alembic/versions/a4d2b9c7e1f0_add_storylet_effects_column.py`
- `src/api/author/suggest.py`
- `src/services/storylet_ingest.py`
- `src/services/storylet_selector.py`
- `src/services/turn_service.py`
- `src/services/world_memory.py`
- `tests/service/test_storylet_selector.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [x] Storylets can declare structured effects independent of narration text.
- [x] Effects are validated and applied server-side via the reducer path.
- [x] Effect application is recorded and replayable via world event history.
- [x] Existing storylets without effects continue to work unchanged.

## Validation Commands

- `python -m pytest tests/service/test_storylet_selector.py -q`
- `python -m pytest tests/api/test_game_endpoints.py -q`
- `python scripts/dev.py lint-all`
- `python -m pytest -q`
- `npm --prefix client run build`

## Rollback Notes

- Revert this item's Storylet `effects` schema/model/migration changes and turn-orchestration effect commit wiring.
- No irreversible data migrations are introduced; the new column is additive and nullable/defaulted.
