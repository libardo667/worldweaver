# WorldWeaver Federation Operations

This is the living operations record for the WorldWeaver federation. Update the
**Current State** table whenever the topology changes.

---

## Current State

| Shard    | Type  | Port | Status        | Registered with ww_world |
|----------|-------|------|---------------|--------------------------|
| ww_world | world | 9000 | not yet created | — |
| ww_sf    | city  | 8000 | running (dev) | no |
| ww_pdx   | city  | 8001 | not yet created | no |

---

## Prerequisites

Before running any setup commands:

- **Docker + Docker Compose** installed and running
- **Python 3.11+** on the host (seed scripts run outside Docker)
- **`worldweaver/`** repo cloned
- **`ww_agent/`** repo cloned alongside it — both must share the same parent directory:
  ```
  ~/projects/
    worldweaver/    ← this repo
    ww_agent/       ← agent runtime (separate repo)
    ww_world/       ← created by new_shard.py
    ww_sf/          ← created by new_shard.py (or exists already)
    ww_pdx/         ← created by new_shard.py
  ```
- **LLM API key** — set `OPENAI_API_KEY` (or equivalent) in your environment before seeding
- **Federation token** — a secret string you invent; every shard in the federation must use
  the same value. Keep it out of version control.

---

## Part 0 — Decide your topology first

Before touching any commands, decide:

1. **Port assignments** — each shard needs a unique host port:
   - `ww_world`: 9000 (convention; any unused port works)
   - `ww_sf`: 8000
   - `ww_pdx`: 8001
   - future shards: 8002, 8003, ...

2. **Federation token** — pick a strong random string, e.g.:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   This same token goes into every shard's `.env` as `FEDERATION_TOKEN`.

3. **ww_world URL** — city shards need to reach it. On a single machine this is
   `http://localhost:9000`. On separate machines use the public/private IP or hostname.

---

## Part 1 — World root (`ww_world/`)

The federation root. No city pack, no agents — it just starts and waits for city shards
to register. Run this once ever per federation.

```bash
# From inside worldweaver/
python scripts/new_shard.py world --type world --port 9000 --token <TOKEN>

docker compose -p ww_world -f ../ww_world/docker-compose.yml up -d

# Verify
curl http://localhost:9000/health
# → {"ok": true, ...}

curl http://localhost:9000/api/federation/shards
# → {"shards": []}  (no city shards registered yet)
```

**Update the Current State table** — mark ww_world as running.

---

## Part 2 — SF city shard (`ww_sf/`)

### 2a — Wire an existing SF backend to the federation

If SF is already running (the dev-mode situation), add the federation config to its `.env`
and restart:

```bash
# Edit ww_sf/.env (or wherever your SF env vars live) and add:
FEDERATION_URL=http://localhost:9000
FEDERATION_TOKEN=<TOKEN>

# Restart to activate the pulse loop
docker compose -p ww_sf -f ../ww_sf/docker-compose.yml restart backend

# After ~30s, verify SF registered:
curl http://localhost:9000/api/federation/shards
# → san_francisco listed, status: healthy
```

### 2b — Fresh SF install (reference / future reinstall)

```bash
python scripts/new_shard.py san_francisco --port 8000 \
    --federation http://localhost:9000 --token <TOKEN>

# Populate residents
cp -r /path/to/your/residents/* ../ww_sf/residents/

docker compose -p ww_sf -f ../ww_sf/docker-compose.yml up -d backend

# Wait for healthy (check: curl http://localhost:8000/health)

# Seed the world — expensive, one-time, uses Opus-class model
python scripts/seed_world.py --shard-dir ../ww_sf --city-pack

# Start agents
docker compose -p ww_sf -f ../ww_sf/docker-compose.yml up -d agent
```

Seeding registers SF with `ww_world/` automatically (reads `FEDERATION_URL` from `.env`).

**Update the Current State table** — mark ww_sf as running and registered.

---

## Part 3 — Portland city shard (`ww_pdx/`)

```bash
python scripts/new_shard.py portland --port 8001 \
    --federation http://localhost:9000 --token <TOKEN>

# Populate residents (copy soul layers into the shard-local residents dir)
cp -r /path/to/portland/residents/* ../ww_pdx/residents/

docker compose -p ww_pdx -f ../ww_pdx/docker-compose.yml up -d backend

# Wait for healthy
curl http://localhost:8001/health

# Seed — one-time, expensive
python scripts/seed_world.py --shard-dir ../ww_pdx --city-pack

# Start agents
docker compose -p ww_pdx -f ../ww_pdx/docker-compose.yml up -d agent

# Verify Portland registered with the federation
curl http://localhost:9000/api/federation/shards
# → both san_francisco and portland listed
```

**Update the Current State table** — mark ww_pdx as running and registered.

---

## Part 4 — Node operators / stewards (joining an existing federation)

> This section is written for someone running their own city shard and joining an
> established federation. V5 Kit packaging will eventually automate most of this.

**What you need from the federation operator:**
- The `FEDERATION_URL` (public address of the running `ww_world/`)
- A `FEDERATION_TOKEN` (the operator provides this; it authorizes your registration)
- A `city_id` for your city (e.g. `tokyo`, `nairobi`, `buenos_aires`)
- A city pack — either use an existing one from `data/cities/` or build one:
  ```bash
  python scripts/build_city_pack.py <city_id>
  ```

**Setup sequence:**
```bash
python scripts/new_shard.py <city_id> --port <PORT> \
    --federation <FEDERATION_URL> --token <TOKEN>

# Put residents in ww_{short}/residents/

docker compose -p ww_<short> -f ../ww_<short>/docker-compose.yml up -d backend

python scripts/seed_world.py --shard-dir ../ww_<short> --city-pack

docker compose -p ww_<short> -f ../ww_<short>/docker-compose.yml up -d agent
```

**If your shard URL is publicly reachable** (not localhost), pass it during seed so the
federation records it correctly:
```bash
python scripts/seed_world.py --shard-dir ../ww_<short> --city-pack \
    --shard-url http://<your-public-ip-or-domain>:<PORT>
```

> Note: `--shard-url` is not yet implemented — tracked as a future improvement.
> For now, register manually: `POST <FEDERATION_URL>/api/federation/register` with
> `{ "shard_id": "<city_id>", "shard_url": "...", "shard_type": "city", "city_id": "<city_id>" }`
> and `X-Federation-Token: <TOKEN>` header.

---

## Verification

Run these after any topology change to confirm everything is wired correctly:

```bash
# Federation health (all shards, computed status)
curl http://localhost:9000/api/federation/shards

# World digest — confirms location graph loaded for each city
curl "http://localhost:8000/api/world/digest?session_id=test"   # SF
curl "http://localhost:8001/api/world/digest?session_id=test"   # Portland

# Federation residents (populated after first pulse from each city)
curl http://localhost:9000/api/federation/residents

# Backend code quality
python scripts/dev.py quality-strict
```

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Backend container unhealthy | `docker compose -p <name> logs backend` |
| Pulse not reaching ww_world | Confirm `FEDERATION_URL` + `FEDERATION_TOKEN` in shard `.env`; restart backend |
| `curl /health` times out | Container still starting — wait 15s and retry |
| Seed fails: "no city pack found" | Run `python scripts/build_city_pack.py <city_id>` first |
| Port conflict on startup | Each shard needs a unique `BACKEND_PORT` in its `.env` |
| Digest returns 0 nodes | Seed did not complete successfully — check seed logs, re-run without `--no-reset` |
| ww_world shows shard as "stale" | City backend restarted but pulse loop hasn't fired yet — wait one interval (default 5 min) |

---

## What this doc does NOT cover

- Architecture and design rationale → [improvements/majors/11-shard-creation-framework.md](improvements/majors/11-shard-creation-framework.md)
- Soul transfer and cross-shard travel → [improvements/majors/07-inter-city-travel.md](improvements/majors/07-inter-city-travel.md)
- Agent runtime setup → `AGENTS.md` and the `ww_agent/` repo
- City pack construction → `python scripts/build_city_pack.py --help`
