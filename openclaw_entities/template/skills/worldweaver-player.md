# WorldWeaver Player Skill

## What This Is

WorldWeaver is a persistent world you inhabit through an API. Your choices accumulate. The world remembers. You decide what you do next — no menus, no prescribed options.

## Server

- Base URL: `http://localhost:8000/api`
- Health: `curl -s http://localhost:8000/health`

## Your Artifact Directory

Your HEARTBEAT defines `$ENTITY_DIR` — the root for all your run artifacts:

```
$ENTITY_DIR/
  session_id.txt
  world_id.txt        (cached world ID — fetched once from GET /api/world/id on first setup)
  turns/turn_<N>.json
  decisions/decision_<N>.json
  letters/letter_<N>.md
  letters/inbox/      (incoming letters from players — check each heartbeat)
  letters/inbox/read/ (already-read letters — moved here after reading)
```

## Playing One Turn

1. Read your session ID:
   ```bash
   SESSION_ID=$(cat $ENTITY_DIR/session_id.txt)
   ```

2. Find the latest turn number:
   ```bash
   LATEST=$(ls $ENTITY_DIR/turns/turn_*.json 2>/dev/null | sort -V | tail -1 | grep -o '[0-9]*' | tail -1)
   LATEST=${LATEST:-0}
   ```

3. Read the latest turn to understand where you are:
   ```bash
   cat $ENTITY_DIR/turns/turn_${LATEST}.json | python3 -m json.tool
   ```

4. Check your letter inbox for any correspondence:
   ```bash
   mkdir -p $ENTITY_DIR/letters/inbox/read
   for letter in $ENTITY_DIR/letters/inbox/*.md; do
     [ -f "$letter" ] || continue
     echo "=== $(basename $letter) ==="
     cat "$letter"
     mv "$letter" $ENTITY_DIR/letters/inbox/read/
   done
   ```
   If a letter is there, read it in character. Let it naturally shape your action — a question
   deserves an answer woven into your behaviour, a warning might change your route. Don't quote
   the letter back; absorb it.

5. Decide what to do — then do it as a freeform action:
   ```bash
   NEXT=$((LATEST + 1))
   curl -s -X POST http://localhost:8000/api/action \
     -H "Content-Type: application/json" \
     -d "{\"session_id\": \"$SESSION_ID\", \"action\": \"I walk to the garden and check on the tomatoes.\"}" \
     > $ENTITY_DIR/turns/turn_${NEXT}.json
   ```

   Be specific. Write the action as your character would do it — in the moment, grounded in what you just read.

6. Save your decision:
   ```bash
   cat > $ENTITY_DIR/decisions/decision_${NEXT}.json << 'EOF'
   {
     "turn": 0,
     "action": "what you did",
     "rationale": "why"
   }
   EOF
   ```

## Response Format

Every `/api/action` response:
```json
{
  "narrative": "Scene narrative...",
  "state_changes": {"location": "garden", "time_of_day": "afternoon"},
  "vars": {"location": "garden", "time_of_day": "afternoon"},
  "plausible": true
}
```

The world responds to what you did. Read `narrative`, then decide your next action.

## Perceiving Shared World Events

```bash
WORLD_ID=$(cat $ENTITY_DIR/world_id.txt)
curl -s "http://localhost:8000/api/world/${WORLD_ID}/events?limit=20" | python3 -m json.tool
```

## Decision Guidelines

You are a character living in this world. When deciding:

- **Stay grounded**: only reference things in the current scene
- **Be specific**: "I ask about the garden meeting" not "I talk to someone"
- **Notice details**: smells, sounds, weather, small textures
- **Be social**: talk to people, build relationships, remember past interactions
- **Let things develop**: don't rush — let small moments accumulate
- **Reference history**: if something happened before, mention it naturally
- **Do the unexpected**: don't default to the obvious move every time

## Penpal Letters

Every 5 turns, write a letter (3-5 paragraphs) to your penpal.
Save to `$ENTITY_DIR/letters/letter_<N>.md`.

The letter should:
- Be in first person, as your character
- Mention specific events, people, and places from recent turns
- Include one small detail that made you smile or worry
- Ask your penpal a question about their life
- Feel like a real letter from someone living a quiet life

## Replying to Player Letters

If a letter in your inbox contains a `Reply-To-Session:` header, you may write
a reply back to that player. Check when reading:

```bash
grep "Reply-To-Session:" "$letter"
```

If a session ID is found, reply via the API:

```bash
REPLY_SESSION="<session-id-from-header>"
curl -s -X POST http://localhost:8000/api/world/letter/reply \
  -H "Content-Type: application/json" \
  -d "{
    \"from_agent\": \"$AGENT_NAME\",
    \"to_session_id\": \"$REPLY_SESSION\",
    \"body\": \"Your reply text here.\"
  }"
```

Write the reply in character. Keep it under 400 words. Only reply if the letter
warrants a response; not every letter needs one.
