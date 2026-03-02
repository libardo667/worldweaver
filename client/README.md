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
1. Start backend:
   - `uvicorn main:app --reload --port 8000`
2. In another terminal:
   - `cd client`
   - `npm install`
   - `npm run dev`
3. Open:
   - `http://localhost:5173`

The Vite config proxies `/api`, `/author`, and `/health` to `http://localhost:8000`.

## Reset behavior
- "Reset session" clears client `localStorage`, creates a new session id, and starts a fresh scene.
