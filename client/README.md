# WorldWeaver Client v1 (Explore Mode)

This is the API-first web client for `30-build-api-first-web-client-v1.md`.

## What it does
- Loads scene text and choices from `POST /api/next`.
- Applies choice sets locally and requests the next scene.
- Supports freeform actions via `POST /api/action`.
- Renders a 3x3 compass and moves via `GET/POST /api/spatial/*`.
- Shows world memory via `GET /api/world/history` and `GET /api/world/facts`.
- Displays a collapsible "What Changed" strip computed on the client.
- Persists `session_id` and session vars in `localStorage`.

## Run locally
0. Optional preflight (recommended):
   - `python scripts/dev.py preflight`
1. Start backend:
   - `python scripts/dev.py backend`
   - (fallback) `uvicorn main:app --reload --port 8000`
2. In another terminal:
   - `python scripts/dev.py client`
   - (fallback) `cd client && npm run dev`
3. Open:
   - `http://localhost:5173`
4. Optional local gate checks from repo root:
   - `python scripts/dev.py verify`
   - `python scripts/dev.py lint <touched_python_paths>`

The Vite config proxies `/api`, `/author`, and `/health` to `http://localhost:8000`.

## Reset behavior
- "Reset session" clears client `localStorage`, creates a new session id, and starts a fresh scene.
- "Dev hard reset" calls `POST /api/dev/hard-reset`, clears client `localStorage`, and rebuilds a clean session thread.
- The "Dev hard reset" button is shown by default in Vite dev mode.
- Override visibility with `VITE_WW_ENABLE_DEV_RESET=1|true|yes` to force show or `0|false|no` to hide.
- The backend route is separately gated by `WW_ENABLE_DEV_RESET` (server env).
