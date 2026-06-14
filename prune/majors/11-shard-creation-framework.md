# Major 11: Shard Creation Framework

**Status:** In Progress (core implementation complete as of 2026-03-14)

**Companion workspace:** `../ww_agent` — agent runtime; residents live here under `residents/`

---

## Problem

WorldWeaver started as a single city (SF). The vision is a fractal hierarchy of named
shards, each running the same base server code but at different scales. Before adding
Portland (or any future city), we need a framework for creating and managing these shards
so the architecture doesn't become a tangled mess of one-off configs.

---

## Design

### The Three-Layer Resident Model

Every resident has three distinct layers:

| Layer | Contents | Portable? |
|-------|----------|-----------|
| **Soul** | `identity/` (SOUL.md, IDENTITY.md, soul_notes.md, tuning.json), `memory/long_term.json`, `memory/reveries.json`, `memory/impressions/` | Yes — travels with the resident |
| **Runtime** | `turns/`, `decisions/`, `session_id.txt`, `world_id.txt`, `memory/working.json` | No — shard-local, left behind |
| **World impact** | World events, facts, graph nodes in shard DB | No — permanent in originating shard |

### Resident Identity

- `resident_id`: opaque UUID stored in `identity/resident_id.txt` — durable, never changes
- `name`: display slug ("elian", "margot") — human-facing, stable in practice
- `session_id`: local embodiment instance — rewritten on arrival at destination shard
- `home_shard` / `current_shard`: governance and location state in federation

### Shard Structure

```
ww_{shard}/
  .env                    ← CITY_ID, BACKEND_PORT, SHARD_TYPE, FEDERATION_URL,
                             CITY_DB_FILE, FEDERATION_TOKEN
  docker-compose.yml      ← mounts ../worldweaver (shared code)
  db/
    worldweaver_{shard}.db
  data/
    world_id_{shard}.txt
  residents/              ← canonical per-shard residents (NOT a symlink)
```

The `worldweaver/` repo is mounted as a volume — one codebase, zero code duplication.

### Fractal Hierarchy

```
ww_world/       ← root federation; resident registry, cross-shard DM mailbox
  ww_sf/        ← SF city shard
    ww_mission/ ← (future) neighborhood shard
  ww_pdx/       ← Portland city shard
```

### Shard Types

| `SHARD_TYPE` | Role |
|-------------|------|
| `world` | Federation root; activates federation endpoints; no simulation loops |
| `city` | Standard world simulation; pushes pulse to FEDERATION_URL |
| `neighborhood` | Sub-city shard (future); pushes to parent city shard |

### Shard Health Semantics

Based on `FEDERATION_PULSE_INTERVAL_SECONDS` (default 300s):
- **healthy** — last pulse within 2× interval
- **degraded** — within 5× interval
- **stale** — beyond 5× interval
- **offline** — deregistered or stale > 24h

### World Pulse

City shards POST to `FEDERATION_URL/api/federation/pulse` every N seconds. Payload
includes `pulse_seq` (monotonic) and `sent_at` for out-of-order protection. `ww_world/`
ignores pulses with `pulse_seq` ≤ last accepted. Pulse response includes any pending
cross-shard DMs for the shard (mailbox delivery).

### Federation Token Auth

All federation write endpoints require `X-Federation-Token` matching `FEDERATION_TOKEN`
env var. Simple pre-shared key — not PKI. Each shard's `.env` has the token.

---

## Implementation

### New files
- `src/api/federation/routes.py` — federation endpoints (register, deregister, pulse, shards, residents, traveler, mailbox, dm)
- `src/api/federation/__init__.py`
- `src/services/federation_pulse.py` — background pulse loop for city shards
- `scripts/new_shard.py` — shard directory creation script
- `alembic/versions/c3d4e5f6a7b8_add_federation_tables.py`

### Modified files
- `src/config.py` — `city_id`, `shard_type`, `federation_url`, `federation_pulse_interval`, `city_db_file`, `federation_token`
- `src/api/game/state.py` — city-aware `_WORLD_ID_FILE = data/world_id_{city_id}.txt`
- `src/api/game/world.py` — replace hardcoded `city_id = "san_francisco"` with `settings.city_id`
- `src/services/world_memory.py` — `get_location_graph(city_id=None)` with per-city cache
- `src/models/__init__.py` — `FederationShard`, `FederationResident`, `FederationTraveler`, `FederationMessage`
- `src/services/city_pack_seeder.py` — load `inter_city.json` as `WorldEdge` records
- `main.py` — register federation router (world shard only); start pulse loop (city shard only)
- `scripts/seed_world.py` — `--shard-dir`, `--federation-url`, `--federation-token`

---

## Usage

### Create Portland shard

```bash
# 1. Create directory
python scripts/new_shard.py portland --port 8001 \
    --federation http://localhost:9000 --token my-secret

# 2. Add residents to ww_pdx/residents/

# 3. Start backend
docker compose -p ww_pdx -f ww_pdx/docker-compose.yml up -d backend

# 4. Seed world (auto-reads .env from shard dir)
python scripts/seed_world.py --shard-dir ../ww_pdx --city-pack

# 5. Start agents
docker compose -p ww_pdx -f ww_pdx/docker-compose.yml up -d agent
```

### Create world federation root

```bash
python scripts/new_shard.py world --type world --port 9000 --token my-secret
docker compose -p ww_world -f ww_world/docker-compose.yml up -d
```

---

## Open Seams

### Soul transfer bundle (implement when first cross-shard travel happens)

```json
{
  "bundle_version": 1,
  "created_at": "...",
  "source_shard": "san_francisco",
  "resident_id": "uuid-...",
  "files": {
    "identity/SOUL.md": "...",
    "identity/resident_id.txt": "uuid-...",
    "memory/long_term.json": "...",
    "memory/reveries.json": "...",
    "memory/impressions/": { ... }
  }
}
```

NOT transferred: `memory/working.json`, `turns/`, `decisions/`.
`session_id.txt` is rewritten on arrival with new timestamp.
Endpoint shape: `GET /api/federation/traveler/{resident_id}/soul`

Future: cryptographically sign/checksum transfer bundles.

### Multi-level pulse chain

Neighborhood shards push to parent city shard (not `ww_world/` directly). City shards
will need inbound aggregation endpoints when neighborhoods land.

### `ww_world/` founding

`ww_world/` isn't seeded — it just starts. The founding event is the first city calling
`POST /api/federation/register`. `new_shard.py --type world` creates the directory.
