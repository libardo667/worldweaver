# WorldWeaver Player Skill

## What This Is

WorldWeaver is a persistent world you inhabit through an API. Your choices
accumulate. The world remembers. You interact by making curl requests.

## Server

- Base URL: `http://localhost:8000/api`
- Health: `curl -s http://localhost:8000/health`

## Your Artifact Directory

Your HEARTBEAT defines `$ENTITY_DIR` — the root for all your run artifacts.
Everything goes under that directory:

```
$ENTITY_DIR/
  session_id.txt
  world_id.txt        (residents only — the founder's session_id)
  turns/turn_<N>.json
  decisions/decision_<N>.json
  letters/letter_<N>.md
```

## First Time Setup

Run these steps only if `$ENTITY_DIR/session_id.txt` does NOT exist.
Your HEARTBEAT has the entity-specific bootstrap payload.

1. Check server health.

2. Create directories:
   ```bash
   mkdir -p $ENTITY_DIR/turns $ENTITY_DIR/decisions $ENTITY_DIR/letters
   ```

3. Generate a session ID:
   ```bash
   echo "<entity-name>-$(date +%Y%m%d-%H%M%S)" > $ENTITY_DIR/session_id.txt
   SESSION_ID=$(cat $ENTITY_DIR/session_id.txt)
   ```

4. Run the bootstrap curl from your HEARTBEAT.

5. Get the first scene:
   ```bash
   curl -s -X POST http://localhost:8000/api/next \
     -H "Content-Type: application/json" \
     -d "{\"session_id\": \"$SESSION_ID\", \"vars\": {}}" \
     > $ENTITY_DIR/turns/turn_1.json
   ```

## Bootstrap API

**Founder** (creates the world):
```bash
curl -s -X POST http://localhost:8000/api/session/bootstrap \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"world_theme\": \"...\",
    \"player_role\": \"...\",
    \"tone\": \"...\",
    \"storylet_count\": 8,
    \"bootstrap_source\": \"openclaw-agent\"
  }"
```

**Resident** (joins an existing world — add `world_id`):
```bash
WORLD_ID=$(cat $ENTITY_DIR/world_id.txt)
curl -s -X POST http://localhost:8000/api/session/bootstrap \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"world_id\": \"$WORLD_ID\",
    \"world_theme\": \"...\",
    \"player_role\": \"...\",
    \"tone\": \"...\",
    \"storylet_count\": 8,
    \"bootstrap_source\": \"openclaw-agent\"
  }"
```

## Playing One Turn

1. Read session ID:
   ```bash
   SESSION_ID=$(cat $ENTITY_DIR/session_id.txt)
   ```

2. Find the latest turn number:
   ```bash
   LATEST=$(ls $ENTITY_DIR/turns/turn_*.json 2>/dev/null | sort -V | tail -1 | grep -o '[0-9]*' | tail -1)
   LATEST=${LATEST:-0}
   ```

3. Read the latest turn:
   ```bash
   cat $ENTITY_DIR/turns/turn_${LATEST}.json | python3 -m json.tool
   ```

4. Decide what to do. Then either:

   **Option A — Pick a choice:**
   ```bash
   NEXT=$((LATEST + 1))
   curl -s -X POST http://localhost:8000/api/next \
     -H "Content-Type: application/json" \
     -d "{\"session_id\": \"$SESSION_ID\", \"vars\": {\"some_var\": true}}" \
     > $ENTITY_DIR/turns/turn_${NEXT}.json
   ```

   **Option B — Freeform action:**
   ```bash
   NEXT=$((LATEST + 1))
   curl -s -X POST http://localhost:8000/api/action \
     -H "Content-Type: application/json" \
     -d "{\"session_id\": \"$SESSION_ID\", \"action\": \"I walk to the garden and check on the tomatoes.\"}" \
     > $ENTITY_DIR/turns/turn_${NEXT}.json
   ```

5. Save your decision:
   ```bash
   cat > $ENTITY_DIR/decisions/decision_${LATEST}.json << 'EOF'
   {
     "turn": 0,
     "mode": "choice or freeform",
     "choice_label": "label if choice",
     "action_text": "what you did if freeform",
     "rationale": "why"
   }
   EOF
   ```

## Response Format

Every `/api/next` and `/api/action` response:
```json
{
  "text": "Scene narrative...",
  "choices": [
    {"label": "Choice description", "set": {"variable": "value"}}
  ],
  "vars": {"location": "corner_cafe", "time_of_day": "morning"}
}
```

When picking a choice, pass that choice's `set` object as `vars` in your next call.

## Perceiving Shared World Events

If you are in a shared world, you can see what others have done:
```bash
WORLD_ID=$(cat $ENTITY_DIR/world_id.txt)
curl -s "http://localhost:8000/api/world/${WORLD_ID}/events?limit=20" | python3 -m json.tool
```

## Decision Guidelines

You are a character living in this world. When deciding:

- **Stay grounded**: only reference things in the current scene
- **Be specific**: "I ask about the garden meeting" not "I talk to someone"
- **Mix it up**: alternate between offered choices and freeform actions
- **Notice details**: smells, sounds, weather, small textures
- **Be social**: talk to people, build relationships, remember past interactions
- **Let things develop**: don't rush — let small moments accumulate
- **Reference history**: if something happened before, mention it naturally

## Penpal Letters

Every 5 turns, write a letter (3-5 paragraphs) to your penpal.
Save to `$ENTITY_DIR/letters/letter_<N>.md`.

The letter should:
- Be in first person, as your character
- Mention specific events, people, and places from recent turns
- Include one small detail that made you smile or worry
- Ask your penpal a question about their life
- Feel like a real letter from someone living a quiet life
