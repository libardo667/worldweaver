# World Reset Procedure

Use this when you want to wipe all accumulated world state and start fresh with a new seeded world.

---

## File Location Note (symlink)

WSL `~/.openclaw` is a symlink to the Windows project `.openclaw/`. **Edit files in one place only** — `.openclaw/` in the project root. WSL and Windows see the same files. Never edit in both.

---

## Order of Operations

### 1. Stop the stack

```bash
python scripts/dev.py down
```

Always stop before touching agent files — a heartbeat mid-delete causes corrupted state.

### 2. Delete agent run files (casper, elian, elias, margot, nadia)

Do this in `.openclaw/workspace-{agent}/worldweaver_runs/{agent}/`. For each agent, delete:

- `turns/*`
- `decisions/*`
- `letters/*`
- `session_id.txt`
- `world_id.txt`
- `turn_count.txt` (elias only)

Also delete stale archive directories:

- `worldweaver_runs/{agent}_old_*/`

Delete world-specific memory files inside each workspace:

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

### 7. Re-spawn agents with the new world_id

Agent `HEARTBEAT.md` files have the world_id **hardcoded at spawn time**. After a reset the old id is gone, so agents must be re-spawned or manually patched.

**Recommended — re-spawn via the entity spawner:**

Upload a CSV to `POST /api/entities/spawn-batch` with the new `world_id`. This regenerates each agent's `HEARTBEAT.md` with the correct id embedded and a fresh `entry_location` from the new world bible.

**Quick alternative — patch in place:**

If you want to keep existing SOUL.md / character profiles, just update the hardcoded line in each agent's `HEARTBEAT.md`:

```bash
# Example for margot (run from project root in Windows, or via WSL symlink path)
sed -i 's/WORLD_ID="world-[^"]*"/WORLD_ID="<new-world-id>"/' \
  .openclaw/workspace-margot/HEARTBEAT.md
```

Then delete `session_id.txt` and `world_id.txt` for each agent (already done in step 2) so First Time Setup runs fresh on next heartbeat.

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
| Agent `HEARTBEAT.md` files | no — update manually or re-spawn |

---

## Notes

- Always stop the stack **before** deleting run files to prevent a heartbeat mid-delete.
- `hard-reset` requires `WW_ENABLE_DEV_RESET=true` in your `.env` (default in dev).
- The `worldweaver-pulse` skill (`/worldweaver-pulse`) is a quick way to verify the world is healthy after seeding.
- Current agents: **casper, elian, elias, margot, nadia** (workspace-{name}), **rowan** (workspace/).
