# Move choice `inc`/`dec` application to the server reducer path

## Problem

Choice effects currently use client-side prediction (`applyLocalSet` in
`client/src/App.tsx`) before roundtrip, which obscures operation intent and can
diverge from server authority.

## Proposed Solution

Shift authoritative arithmetic effect handling to the backend:

1. Treat `choice.set` operation payloads as intents sent to the server.
2. Apply `inc`/`dec` operations in the server reducer with validation/clamps.
3. Keep client prediction optional and clearly non-authoritative.

## Files Affected

- `client/src/App.tsx`
- `src/services/game_logic.py`
- `src/api/game/story.py`
- `src/models/schemas.py`
- `tests/service/test_game_logic.py`
- `tests/api/test_game_endpoints.py`

## Acceptance Criteria

- [ ] Choice arithmetic operations are validated and committed server-side.
- [ ] Client/UI state reconciles to server-authoritative vars every turn.
- [ ] Invalid `inc`/`dec` payloads do not crash and are handled consistently.

