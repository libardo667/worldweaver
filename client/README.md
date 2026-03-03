# WorldWeaver Client (Explore Mode)

This client consumes backend APIs (`/api`, `/author`, `/health`) through Vite proxying.

## Recommended runtime path

From repo root:

```bash
python scripts/dev.py stack-up
```

Then open:

- `http://localhost:5173`

Stop:

```bash
python scripts/dev.py stack-down
```

## Manual fallback

From repo root:

```bash
python scripts/dev.py preflight
python scripts/dev.py backend
python scripts/dev.py client
```

## Proxy behavior

- Default proxy target: `http://localhost:8000`
- Compose proxy target: `http://backend:8000` (set via `VITE_PROXY_TARGET`)

## Local checks

From repo root:

```bash
python scripts/dev.py build
python scripts/dev.py verify
```

## Reset behavior

- "Reset session" clears client `localStorage`, creates a new session id, and starts a fresh scene.
- "Dev hard reset" calls `POST /api/dev/hard-reset`, clears client `localStorage`, and rebuilds a clean session thread.
- The "Dev hard reset" button is shown by default in Vite dev mode.
- Override visibility with `VITE_WW_ENABLE_DEV_RESET=1|true|yes` to force show or `0|false|no` to hide.
- The backend route is separately gated by `WW_ENABLE_DEV_RESET` (server env).
