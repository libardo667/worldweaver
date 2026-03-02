# Build an API-first web client v1 and retire Twine as the primary UI

## Problem

`VISION.md` defines Twine as a prototype, but current player experience depends on `twine_resources/WorldWeaver-Twine-Story.twee`. This creates friction for evolving interaction patterns (freeform input, world memory introspection, semantic leads) and limits product direction around a stable API contract.

## Proposed Solution

1. Build a dedicated web client (single-page app) that consumes existing FastAPI endpoints:
   - session start/resume
   - next storylet
   - freeform action
   - spatial navigation
   - world history/facts
2. Generate or maintain typed API client bindings from OpenAPI.
3. Implement core UX loops:
   - narrative stream with choices and freeform command entry
   - visible location and semantic lead hints
   - world memory panel showing recent facts
4. Keep feature parity with Twine for current gameplay flows before adding new UI features.
5. Move Twine story to legacy/demo status once parity is reached.

## Files Affected

- `frontend/*` (new)
- `src/api/game.py` (contract hardening as needed)
- `src/models/schemas.py` (response consistency)
- `tests/contract/*` (expand for new frontend contract guarantees)
- `twine_resources/WorldWeaver-Twine-Story.twee` (deprecation notice/update)

## Acceptance Criteria

- [ ] Player can complete core loop (next, choice, freeform, move) in the new web client.
- [ ] Client handles API errors and reconnect states gracefully.
- [ ] World history/facts are visible in the client without direct DB access.
- [ ] Twine is no longer required for normal development and manual testing.
- [ ] Contract tests prevent breaking key frontend payload shapes.

## Risks & Rollback

UI rewrite risk is scope creep and delayed gameplay progress. Keep strict parity-first scope and avoid redesigning backend semantics in the same milestone. Roll back by keeping Twine as a fallback client until parity is proven.
