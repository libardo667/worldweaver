# WorldWeaver commons client

The public-facing client: a full-viewport living map of a shard's town, with
everything else side-loading over it. A stranger lands on the threshold
(`look around` / `join the world`), walks the town as a sessionless spectator
(place panels: who's here, what's overheard, what's on the stoop, where you
can walk), and can join natively (register/login → session bootstrap) to
speak, walk, make and carry objects, give or exchange them with someone present,
leave, take, or reclaim them from stoops, and knock at controlled doors. A
place controller can answer knocks and change that exact door's rule without
receiving a town-wide access dashboard. Place URLs (`/place/mill-reach`)
are shareable deep links.

## Run

```bash
python dev.py client                   # from the repo root; Vite on :5174
python dev.py client-public            # explicit alias
VITE_PROXY_TARGET=http://localhost:8004 npm run dev   # point at a specific shard
```

The dev proxy sends `/api` + `/health` to `VITE_PROXY_TARGET` (default
`:8000`) and `/ww-world/*` to the federation root (`VITE_WW_WORLD_URL`,
default `:9000`). Build with `npm run build` (tsc + vite; also part of
`python dev.py check`).

## Boundaries (vision, not implementation detail)

This surface centers places and encounter, never shard-wide telemetry. The
API layer (`src/api/ww.ts`) deliberately does not wrap the digest
roster/timeline, rest metrics, roster directory, or vitality endpoints, and
the map API and UI expose occupancy only as counts/glow intensity — a separate
one-place presence read supplies names only while that place's panel is open.
Keep it that way; operator/steward surfaces belong elsewhere
(Major 71).
