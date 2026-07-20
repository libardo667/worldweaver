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

Registration asks for email, a confirmed password, and the shard's terms. The server generates any legacy
username internally; after account creation, a separate step asks for the public name people and residents
will see. Login and password recovery use email. Password-reset email links open the reset form directly;
delivery requires the node to configure its email provider. A steward can require hashed, expiring,
one-use email verification with `WW_REQUIRE_EMAIL_VERIFICATION=true`. This option is off by default, and
readiness fails instead of accepting new accounts when verification is required without working email
configuration.
Federated hosts should set `WW_CLIENT_URL` to this human-facing origin. `WW_PUBLIC_URL` remains the shard
API address; travel discovery and reset mail no longer have to pretend those are the same endpoint.
One client origin can serve several shards through prefixes such as `/ww-sfo` and `/ww-pdx`; each prefix
keeps its API calls on the same browser origin and the unprefixed root remains the selected default shard.
The actor login is shared across those paths, while the temporary session ID and standing place are stored
per shard. Opening Portland can therefore never reuse an Alderbank incarnation by accident.

Available inter-city routes appear only while a participant is standing at that route's local gateway.
Departure retires the source presence before redirecting to the destination client. The redirect carries
only a random travel ID; the destination uses the normal actor login and can safely retry an interrupted
arrival. A shared-origin local setup keeps one actor login across its city prefixes, while separately hosted
sites ask the traveler to sign in again.

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
