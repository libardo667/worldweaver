# HEARTBEAT.md — Elian

## Artifact Root

```bash
ENTITY_DIR=~/worldweaver_runs/elian
```

All paths below use `$ENTITY_DIR` as the root.

---

## WorldWeaver Check-in

Every heartbeat, do the following:

1. Check if the WorldWeaver server is running:
   ```bash
   curl -s http://localhost:8000/health
   ```
   If the server is down, reply HEARTBEAT_OK and skip everything else.

2. Check if `$ENTITY_DIR/session_id.txt` exists.
   - If it does NOT exist, follow the **First Time Setup** instructions in
     `~/.openclaw/workspace/skills/worldweaver-player.md`, using the paths
     and bootstrap payload defined below.

3. Read your session ID:
   ```bash
   SESSION_ID=$(cat $ENTITY_DIR/session_id.txt)
   ```

4. Play exactly ONE turn:
   - Get the current scene from the WorldWeaver API.
   - Make a decision as Elian — pick a choice or take a freeform action.
   - Save the turn JSON to `$ENTITY_DIR/turns/turn_<N>.json`.
   - Save your decision to `$ENTITY_DIR/decisions/decision_<N>.json`.
   - Refer to `~/.openclaw/workspace/skills/worldweaver-player.md` for exact
     API calls and decision guidelines.

5. Count how many turn files exist in `$ENTITY_DIR/turns/`.
   If the count is a multiple of 5, write a penpal letter to
   `$ENTITY_DIR/letters/letter_<N>.md`.

6. If nothing noteworthy happened, reply HEARTBEAT_OK.
   If something interesting happened, send a one-sentence summary like:
   "Played a WorldWeaver turn as Elian — finally met the neighbor with the loud wind chimes."

---

## Elian's Bootstrap Payload (First Time Setup only)

```bash
mkdir -p $ENTITY_DIR/turns $ENTITY_DIR/decisions $ENTITY_DIR/letters
echo "elian-$(date +%Y%m%d-%H%M%S)" > $ENTITY_DIR/session_id.txt
SESSION_ID=$(cat $ENTITY_DIR/session_id.txt)
```

Bootstrap the world (Elian is the **founder** — no world_id needed):
```bash
curl -s -X POST http://localhost:8000/api/session/bootstrap \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"world_theme\": \"cozy neighborhood slice-of-life\",
    \"player_role\": \"quiet cartographer with a balcony garden\",
    \"description\": \"A quiet residential cul-de-sac where small daily rhythms shape a community. Gardens, borrowed tools, shared meals, slow-building friendships.\",
    \"key_elements\": [\"community garden\", \"corner cafe with good light\", \"block party planning\", \"the dog that visits everyone\", \"heirloom tomatoes\"],
    \"tone\": \"warm, observant, unhurried\",
    \"storylet_count\": 8,
    \"bootstrap_source\": \"openclaw-agent\"
  }"
```

After bootstrapping, save the session_id as the world_id so other residents
can reference it:
```bash
cp $ENTITY_DIR/session_id.txt $ENTITY_DIR/world_id.txt
```

Then get the first scene:
```bash
curl -s -X POST http://localhost:8000/api/next \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"vars\": {}}" \
  > $ENTITY_DIR/turns/turn_1.json
```
