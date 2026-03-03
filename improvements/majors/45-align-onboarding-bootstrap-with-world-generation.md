# Align onboarding bootstrap with generated world critical path

## Problem
The current "reset -> onboarding -> first storylet" path is not aligned with `VISION.md`:

- The client collects onboarding inputs (`world_theme`, `player_role`) but bootstraps by calling `/api/next` directly (`client/src/App.tsx:43-44`, `client/src/App.tsx:218-223`, `client/src/App.tsx:238-250`, `client/src/App.tsx:531-546`).
- `/api/next` sets vars and immediately runs `ensure_storylets` + selector (`src/api/game/story.py:25-30`), and `ensure_storylets` exits early once enough eligible rows already exist (`src/services/game_logic.py:50-57`).
- Startup and reset both reseed legacy test storylets (`main.py:51`, `src/api/game/state.py:226-238`, `src/services/seed_data.py:17-49`), so first turns can come from "Test *" rows instead of onboarding-shaped world generation.
- `DEFAULT_SESSION_VARS` still injects `has_pickaxe=True` into every new session (`src/services/seed_data.py:10-13`, `src/services/session_service.py:101-102`).
- A generated world endpoint exists (`src/api/author/world.py:42-64`) but is not used by the onboarding flow (no client references to `generate-world`).

As a result, the first player-visible story beat can be dominated by legacy seed state instead of the player-authored world setup.

## Proposed Solution
Implement an explicit bootstrap critical path that binds onboarding input to world initialization before first scene selection.

1. Add an explicit session bootstrap contract
   - Add `POST /api/session/bootstrap` for onboarding payload intake and bootstrap orchestration.
   - Persist bootstrap provenance markers (source, timestamp, inputs hash, bootstrap status) in session state.

2. Create a reusable bootstrap service for world initialization
   - Extract world generation orchestration from `/author/generate-world` into a service reusable by both author tools and session bootstrap.
   - Avoid route-level destructive logic in onboarding path; keep destructive world reset explicit and intentional.

3. Decouple production startup/reset from legacy test seed data
   - Make legacy "Test *" seed insertion opt-in (dev/test flag), not default runtime behavior.
   - Replace player defaults with neutral baseline vars; do not auto-grant `has_pickaxe`.

4. Wire client onboarding to bootstrap
   - On "Start this world", call bootstrap endpoint first, then request `/api/next`.
   - Keep onboarding visible on bootstrap failure and show actionable error toast.

5. Add regression coverage for the critical path
   - Add tests for reset semantics, bootstrap semantics, and first-turn source behavior.
   - Add checks that onboarding vars influence generated opening context.

## Files Affected
- `src/api/game/state.py`
- `src/api/game/story.py`
- `src/api/author/world.py`
- `src/models/schemas.py`
- `src/services/seed_data.py`
- `src/services/session_service.py`
- `src/services/game_logic.py`
- `src/services/world_bootstrap_service.py` (new)
- `src/config.py`
- `main.py`
- `client/src/App.tsx`
- `client/src/api/wwClient.ts`
- `client/src/state/sessionStore.ts`
- `tests/api/test_game_endpoints.py`
- `tests/api/test_state_endpoints.py`
- `tests/services/test_session_service.py`

## Acceptance Criteria
- [ ] `POST /api/reset-session` does not reseed legacy "Test *" storylets by default.
- [ ] `POST /api/session/bootstrap` accepts onboarding inputs and marks bootstrap provenance in session state.
- [ ] Client onboarding calls bootstrap before the first `/api/next` request for a new/reset world.
- [ ] The first scene after onboarding is selected from bootstrap-generated/storylet-runtime candidates, not legacy test seed rows.
- [ ] New sessions do not receive `has_pickaxe` unless explicitly set by gameplay/bootstrap payload.
- [ ] `/author/generate-world` behavior remains available for author workflows.
- [ ] `python -m pytest -q` passes.

## Risks & Rollback
Main risk is introducing ordering bugs between reset, bootstrap, and first `/api/next`. Roll back safely by feature-flagging the new bootstrap path and retaining legacy flow behind explicit opt-in flags while tests are stabilized. If generation reliability regresses, keep bootstrap contract and temporarily use deterministic non-test fallback storylets instead of LLM generation.
