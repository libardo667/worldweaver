# PR Evidence: Minor 89 - Add Storylet Effects Contract and Server Application

## Item

`improvements/minors/archive/89-add-storylet-effects-contract-and-server-application.md`

## Scope

Implemented an additive, typed storylet `effects` contract and wired deterministic server-side application through the authoritative reducer at storylet fire and choice-commit time.

## What Changed

| File | Change |
|------|--------|
| `src/models/schemas.py` | Added typed storylet effect operations (`set`, `increment`, `append_fact`) with `when` trigger (`on_fire` / `on_choice_commit`); extended `StoryletIn` with normalized `effects`. |
| `src/models/__init__.py` | Added `effects` JSON column to `Storylet` model. |
| `alembic/versions/a4d2b9c7e1f0_add_storylet_effects_column.py` | Added additive migration for `storylets.effects`. |
| `src/services/turn_service.py` | Added strict effect-to-`ActionDeltaContract` conversion, reducer-backed application on storylet fire, staged choice-commit effect application, pending effect persistence, and event metadata recording for replay/debug. |
| `src/services/world_memory.py` | Added constants for effect-metadata keys used in persisted world-event metadata. |
| `src/services/storylet_selector.py` | Preserved runtime synthesized candidate `effects` when constructing transient runtime storylets. |
| `src/api/author/suggest.py` | Preserved `effects` when saving suggested storylets with `commit=true`. |
| `src/services/storylet_ingest.py` | Persisted optional `effects` through ingest pipeline outputs. |
| `tests/service/test_storylet_selector.py` | Added coverage for runtime synthesis preserving effect contracts. |
| `tests/api/test_game_endpoints.py` | Added coverage for fire-time effect application + metadata and choice-commit effect application idempotency path. |
| `improvements/ROADMAP.md` | Marked minor `89` complete and advanced active queue/order. |

## Why This Matters

- Moves story-impacting mutations out of narration text and into typed, reducer-controlled operations.
- Makes effect commits deterministic and replayable through world-event history metadata.
- Reduces client trust surface: world/state changes can be authored as server-applied contracts rather than implied prose.
- Improves debugging and comparative playtests by exposing applied effect ops + reducer receipts in persisted event metadata.

## Acceptance Criteria Check

- [x] Storylets can declare structured effects independent of narration text.
- [x] Effects are validated and applied server-side via the reducer path.
- [x] Effect application is recorded and replayable via world event history.
- [x] Existing storylets without effects continue to work unchanged.

## Quality Gate Evidence

### Gate 1: Contract Integrity

- No API route/path/response envelope changes were introduced.
- `StoryletIn` adds an optional additive field (`effects`) and preserves existing payload compatibility.

### Gate 2: Correctness

- `python -m pytest tests/service/test_storylet_selector.py -q` -> `10 passed`
- `python -m pytest tests/api/test_game_endpoints.py -q` -> `49 passed`
- `python -m pytest -q` -> `547 passed, 14 warnings`

### Gate 3: Build and Static Health

- `python scripts/dev.py lint-all` -> pass
- `npm --prefix client run build` -> pass

## Operational Safety / Rollback

- Rollback path: revert this PR's Storylet `effects` model/schema/migration plus turn orchestration effect-application wiring and tests.
- Safe-disable path: remove/guard reducer application blocks in `TurnOrchestrator.process_next_turn` for `on_fire` and `on_choice_commit` effects.
- Migration safety: additive nullable JSON column only; downgrade cleanly drops `storylets.effects`.

## Residual Risk

- Choice-commit effects are staged per-session and applied on the next `/next` call with `choice_taken`; this assumes standard turn sequencing.
- Effect payload quality from authored/generated content remains schema-validated but still requires content governance for design quality.
