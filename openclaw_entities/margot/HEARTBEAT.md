# HEARTBEAT.md — Margot

## Artifact Root

```bash
ENTITY_DIR=~/worldweaver_runs/margot
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
   - If it does NOT exist, follow the **First Time Setup** instructions below.

3. Read your session ID:
   ```bash
   SESSION_ID=$(cat $ENTITY_DIR/session_id.txt)
   ```

4. Play exactly ONE turn:
   - Get the current scene from the WorldWeaver API.
   - Make a decision as Margot — pick a choice or take a freeform action.
   - Save the turn JSON to `$ENTITY_DIR/turns/turn_<N>.json`.
   - Save your decision to `$ENTITY_DIR/decisions/decision_<N>.json`.
   - Refer to `~/.openclaw/workspace/skills/worldweaver-player.md` for exact
     API calls and decision guidelines.

5. Count how many turn files exist in `$ENTITY_DIR/turns/`.
   If the count is a multiple of 5, write a penpal letter to
   `$ENTITY_DIR/letters/letter_<N>.md`.

6. If nothing noteworthy happened, reply HEARTBEAT_OK.
   If something interesting happened, send a one-sentence summary like:
   "Played a WorldWeaver turn as Margot — ran into Elian at the community garden."

---

## Margot's First Time Setup

```bash
mkdir -p $ENTITY_DIR/turns $ENTITY_DIR/decisions $ENTITY_DIR/letters
echo "margot-$(date +%Y%m%d-%H%M%S)" > $ENTITY_DIR/session_id.txt
SESSION_ID=$(cat $ENTITY_DIR/session_id.txt)
```

Find Elian's session ID (this is the shared world_id):
```bash
WORLD_ID=$(cat ~/worldweaver_runs/elian/session_id.txt)
echo "$WORLD_ID" > $ENTITY_DIR/world_id.txt
```

If Elian's file doesn't exist yet, Elian hasn't bootstrapped. Stop and report
that the world founder hasn't set up yet.

Bootstrap as a resident (pass world_id to join Elian's world):
```bash
WORLD_ID=$(cat $ENTITY_DIR/world_id.txt)
curl -s -X POST http://localhost:8000/api/session/bootstrap \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"world_id\": \"$WORLD_ID\",
    \"world_theme\": \"cozy neighborhood slice-of-life\",
    \"player_role\": \"retired letter carrier who has lived here eleven years\",
    \"tone\": \"warm, direct, occasionally overbearing\",
    \"storylet_count\": 8,
    \"bootstrap_source\": \"openclaw-agent\"
  }"
```

Then get the first scene:
```bash
curl -s -X POST http://localhost:8000/api/next \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"$SESSION_ID\", \"vars\": {}}" \
  > $ENTITY_DIR/turns/turn_1.json
```
