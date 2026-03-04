# Add a startup setup modal when API key or model is missing

## Problem

Fresh/local-first users can land in a broken runtime state without realizing it:
- no OpenRouter API key configured,
- no explicit model selected for runtime.

When this happens, the app can appear "alive" but cannot reliably produce turns.
The current flow relies on users knowing to inspect `.env` and/or manually switch
models.

## Proposed Solution

Add a blocking startup setup modal flow that appears whenever runtime setup is
incomplete.

1. Add a backend setup-status endpoint that reports whether runtime has:
   - a usable API key,
   - a valid selected model.
2. Add a startup modal in the client that appears when setup is incomplete.
3. Modal collects:
   - OpenRouter API key (password field),
   - model selection (from current `/api/models` list).
4. On submit:
   - apply key/model to runtime settings,
   - re-check setup status,
   - unblock normal UI only when complete.
5. Keep API keys write-only in API responses/logs.

## Files Affected

- `src/api/game/settings_api.py`
- `src/services/llm_client.py`
- `src/config.py`
- `client/src/App.tsx`
- `client/src/components/*` (new setup modal component)
- `client/src/api/wwClient.ts`
- `client/src/types.ts`

## Acceptance Criteria

- [x] App shows a blocking setup modal on first load when API key or model is missing.
- [x] User can set API key + model from the modal and continue without restart.
- [x] API key is never returned in clear text from any API response.
- [x] Existing model dropdown behavior still works after setup completion.
- [x] `python -m pytest -q` and `npm --prefix client run build` pass.
