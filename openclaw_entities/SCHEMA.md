# OpenClaw Entity Schema

This folder contains WorldWeaver test entities — OpenClaw agent configurations
that can be loaded into an OpenClaw instance to spawn a resident in a shared world.

Each entity is a subdirectory containing three files:

```
openclaw_entities/
  <entity-name>/
    SOUL.md        ← who this entity is
    HEARTBEAT.md   ← what they do each tick
    skills/
      worldweaver-player.md   ← API reference + world setup
```

---

## How to Spawn an Entity

1. Copy the entity's folder contents into your OpenClaw workspace:
   ```
   ~/.openclaw/workspace/
   ```

2. Start the WorldWeaver server if it isn't running:
   ```bash
   cd <worldweaver-repo>
   python scripts/dev.py serve
   ```

3. Trigger a heartbeat in your OpenClaw instance. The agent will read
   `HEARTBEAT.md` and follow the setup/play instructions automatically.

---

## World Roles

| Entity | Role | World mode |
|---|---|---|
| `elian` | Founder — creates a new shared world | `world_id` = own `session_id` |
| `margot` | Resident — joins Elian's world | `world_id` = Elian's `session_id` |

**Founder** = the first entity to bootstrap. Their `session_id` *is* the `world_id`.
All world storylets and the world bible live in their session.

**Resident** = any entity that joins after. They pass `world_id: <founder_session_id>`
in their bootstrap call. Their events are recorded against the shared world log,
and they inherit the founder's world bible.

---

## The Join Flow

A resident's bootstrap call looks like this:

```bash
curl -s -X POST http://localhost:8000/api/session/bootstrap \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"world_id\": \"$WORLD_ID\",
    \"world_theme\": \"cozy neighborhood slice-of-life\",
    \"player_role\": \"retired letter carrier who knows everyone\",
    \"tone\": \"warm, observant\",
    \"storylet_count\": 8,
    \"bootstrap_source\": \"openclaw-agent\"
  }"
```

The `world_id` is the founder's `session_id`. After this call, all of the
resident's events are written to the shared world event log. The narrator
context for each resident includes the full world history — they are aware of
each other's actions.

To find Elian's session_id (if running in the same WSL environment):
```bash
cat ~/worldweaver_runs/elian/session_id.txt
```

---

## Artifact Layout per Entity

Each entity stores its run artifacts under a named subdirectory of
`~/worldweaver_runs/` so they don't collide:

```
~/worldweaver_runs/
  elian/
    session_id.txt
    world_id.txt        ← for residents: the founder's session_id
    turns/
    decisions/
    letters/
  margot/
    session_id.txt
    world_id.txt
    turns/
    decisions/
    letters/
```

---

## Adding a New Entity

1. Create `openclaw_entities/<name>/SOUL.md` — define character, personality,
   and any specific interests or habits.
2. Create `openclaw_entities/<name>/HEARTBEAT.md` — copy from an existing
   entity and update the artifact paths and bootstrap call.
3. Create `openclaw_entities/<name>/skills/worldweaver-player.md` — copy
   from `SCHEMA.md`'s reference or an existing entity. Adjust the
   `player_role` and `world_id` handling.
4. Add a row to the World Roles table above.
