# WorldWeaver Federation Operations

This document now assumes the **shard-first** runtime. Backend and agent secrets belong in each shard's `.env`. `worldweaver_engine/.env` is legacy local-dev scaffolding and should not be relied on for live shard auth, email, or inference configuration.

This is the living operations record for the WorldWeaver federation. Update the
**Current State** table whenever the topology changes.

Shard directories use **IATA airport codes** as short identifiers (`ww_sfo`, `ww_pdx`,
`ww_nrt`, etc.) — unambiguous, universally understood, and pleasingly evocative.

---

## Current State

| Shard     | City ID       | Port | Status            | Registered with ww_world |
|-----------|---------------|------|-------------------|--------------------------|
| ww_world  | —             | 9000 | running (Docker)  | — |
| ww_sfo    | san_francisco | 8000 | seeding (dev)     | no — in progress |
| ww_pdx    | portland      | 8001 | not yet created   | no |

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
    ww_sfo/         ← created by new_shard.py (or migrated from dev)
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
   - `ww_sfo`: 8000
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

## Part 2 — SF city shard (`ww_sfo/`)

### 2a — Seed dev backend and register (current situation)

SF is running in dev mode from the base `worldweaver/` repo. Seed it and wire it to
the federation in one command:

```bash
python scripts/seed_world.py --city-pack \
    --federation-url http://localhost:9000 \
    --federation-token <TOKEN>
```

This seeds `san_francisco` (the default `CITY_ID`) and registers with `ww_world`.
After seeding completes, start agents and verify:

```bash
# Start agents (from ww_agent/ repo)
# ... see AGENTS.md

# Verify SF registered
curl http://localhost:9000/api/federation/shards
# → san_francisco listed, status: healthy
```

### 2b — Migrate to proper ww_sfo/ Docker shard (when going to production)

When ready to move SF off the dev server and onto a proper shard setup:

```bash
python scripts/new_shard.py san_francisco --port 8000 \
    --federation http://localhost:9000 --token <TOKEN>
# → creates ww_sfo/

# Copy the seeded DB into the shard directory
cp db/worldweaver.db ../ww_sfo/db/worldweaver_san_francisco.db

# Copy residents
cp -r /path/to/residents/* ../ww_sfo/residents/

# Stop dev backend, start Docker backend
docker compose -p ww_sfo -f ../ww_sfo/docker-compose.yml up -d backend

# Verify (same port, different runner)
curl http://localhost:8000/health

# Start agents via Docker
docker compose -p ww_sfo -f ../ww_sfo/docker-compose.yml up -d agent
```

No re-seeding required — the DB carries over.

**Update the Current State table** — mark ww_sfo as running and registered.

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
# → creates ww_<iata>/ (e.g. ww_nrt for tokyo)

# Put residents in ww_<iata>/residents/

docker compose -p ww_<iata> -f ../ww_<iata>/docker-compose.yml up -d backend

python scripts/seed_world.py --shard-dir ../ww_<iata> --city-pack

docker compose -p ww_<iata> -f ../ww_<iata>/docker-compose.yml up -d agent
```

**If your shard URL is publicly reachable** (not localhost), pass it during seed so the
federation records it correctly:
```bash
python scripts/seed_world.py --shard-dir ../ww_<iata> --city-pack \
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
curl "http://localhost:8000/api/world/digest?session_id=test"   # SFO
curl "http://localhost:8001/api/world/digest?session_id=test"   # PDX

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
| Digest returns 0 nodes | Seed did not complete — check seed logs, re-run without `--no-reset` |
| ww_world shows shard as "stale" | City backend restarted but pulse loop hasn't fired yet — wait one interval (default 5 min) |

---

## What this doc does NOT cover

- Architecture and design rationale → [improvements/majors/11-shard-creation-framework.md](improvements/majors/11-shard-creation-framework.md)
- Soul transfer and cross-shard travel → [improvements/majors/07-inter-city-travel.md](improvements/majors/07-inter-city-travel.md)
- Agent runtime setup → `AGENTS.md` and the `ww_agent/` repo
- City pack construction → `python scripts/build_city_pack.py --help`
