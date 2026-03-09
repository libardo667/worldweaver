# World Reset Procedure

Use this when you want to wipe all accumulated world state and start fresh with a new seeded world.

---

## Order of Operations

### 1. Stop the stack

```bash
python scripts/dev.py down
```

### 2. Delete agent run files while the stack is down (casper, elian, elias, margot)

For each `workspace-{agent}/worldweaver_runs/{agent}/`, delete:

- `turns/*`
- `decisions/*`
- `letters/*`
- `session_id.txt`
- `world_id.txt`
- `turn_count.txt` (elias only)

Also delete entire stale archive directories:

- `worldweaver_runs/{agent}_old_*/`

Delete world-specific memory files:

- `memory/2026-03-08-*.md` (and any future date-stamped worldweaver memory files)

Check and clear if world-specific:

- **elian**: `BOOTSTRAP.md`
- **margot**: `MEMORY.md`

**Keep untouched:** `AGENTS.md`, `HEARTBEAT.md`, `IDENTITY.md`, `SOUL.md`, `TOOLS.md`, `USER.md`, `skills/worldweaver-player.md`

### 3. Clean up Rowan's workspace (still while stack is down)

```
workspace/worldweaver_runs/rowan_old_*/   ← delete (stale archives)
workspace/worldweaver_runs/rowan/         ← delete if resetting Rowan too, otherwise keep
```

### 4. Restart the stack

```bash
python scripts/dev.py up
```

### 5. Hard-reset the database

```bash
curl -X POST http://localhost:8000/api/dev/hard-reset
```

Wipes all DB tables: events, facts, nodes, edges, projection, session vars, storylets. Resets ID sequences. Clears runtime caches.

### 6. Seed the new world

```bash
curl -X POST http://localhost:8000/api/world/seed \
  -H "Content-Type: application/json" \
  -d '{
    "world_theme": "Oakhaven Lows",
    "player_role": "a resident of the city",
    "tone": "grounded, melancholy, emergent",
    "storylet_count": 12
  }'
```

Note the returned `world_id` — it will also be written to `data/world_id.txt` server-side automatically.

### 7. Agents bootstrap in

Each agent's next heartbeat will call `GET /api/world/id` to get the new `world_id`, then `POST /api/session/bootstrap` to join the world. Their `world_id.txt` and `session_id.txt` will be written fresh on first play.

---

## What the hard-reset clears

| Table | Cleared |
|---|---|
| storylets | yes |
| session_vars | yes |
| world_events | yes |
| world_nodes | yes |
| world_edges | yes |
| world_facts | yes |
| world_projection | yes |
| Runtime caches | yes |
| `data/world_id.txt` | no — overwritten by `/world/seed` |

---

## Notes

- Always stop the stack **before** deleting run files to prevent a heartbeat mid-delete.
- `hard-reset` requires `WW_ENABLE_DEV_RESET=true` in your `.env` (default in dev).
- The `worldweaver-pulse` skill (`/worldweaver-pulse`) is a quick way to verify the world is healthy after seeding.
