# Add a global settings menu for model/key management and runtime controls

## Problem

Model selection is currently exposed in the top bar, but there is no coherent
settings surface for API key management and related runtime controls. This
forces scattered flows and makes operations harder once the app is running.

## Proposed Solution

Add a persistent settings menu/drawer accessible from any mode, starting with
model + provider key controls and leaving room for additional toggles.

1. Add a settings entry point in top bar (gear/menu button).
2. Add settings panel sections:
   - Provider/API key management,
   - Active model selection,
   - Runtime feature toggles (read/write where supported).
3. Reuse existing `/api/models` and `/api/model` endpoints; add secure key
   write endpoint as needed.
4. Show setup/readiness status inline (configured vs missing).
5. Keep Constellation/Create/Reflect/Explore mode behavior unchanged.

## Files Affected

- `client/src/App.tsx`
- `client/src/components/*` (new settings menu components)
- `client/src/api/wwClient.ts`
- `client/src/types.ts`
- `src/api/game/settings_api.py` (if key/toggle endpoints are added)
- `README.md` (operator usage notes)

## Acceptance Criteria

- [ ] Settings menu is available from all app modes.
- [ ] User can change model from settings and see active model update.
- [ ] User can set/update API key from settings without exposing key in responses.
- [ ] Existing top-bar model UX remains functional or is intentionally replaced.
- [ ] Settings surface is mobile-usable and does not block gameplay when closed.
- [ ] `python -m pytest -q` and `npm --prefix client run build` pass.
