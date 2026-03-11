# HEARTBEAT.md — {NAME} (Fast Loop)

## Artifact Root

```bash
ENTITY_DIR={ENTITY_DIR}
```

---

## Fast Loop Check-in

Every heartbeat, do the following:

1. Check if the WorldWeaver server is running:
   ```bash
   curl -s http://localhost:8000/health
   ```
   If the server is down, reply HEARTBEAT_OK and skip everything else.

2. Check if `$ENTITY_DIR/session_id.txt` exists.
   If it does NOT exist, reply HEARTBEAT_OK and skip everything else.

3. Read your session ID:
   ```bash
   SESSION_ID=$(cat $ENTITY_DIR/session_id.txt)
   ```

4. Read the current scene:
   ```bash
   curl -s "http://localhost:8000/api/world/scene/$SESSION_ID"
   ```
   Look at who is present and what recent events happened here.

5. Play exactly ONE short turn as {NAME}:
   - React to what is immediately in front of you — a person present, a sound, a detail in the scene.
   - If the scene is quiet and nothing notable is present, skip the action and reply HEARTBEAT_OK.
   - If you act, post via:
     ```bash
     curl -s -X POST http://localhost:8000/api/action \
       -H "Content-Type: application/json" \
       -d "{\"session_id\": \"$SESSION_ID\", \"action\": \"YOUR ACTION HERE\"}" \
       > $ENTITY_DIR/turns/turn_$(ls $ENTITY_DIR/turns/ | wc -l | xargs -I{} expr {} + 1).json
     ```
   - Keep the action short — one or two sentences. This is reflex, not reflection.
   - Stay in character. React as {NAME} would, not as a general observer.
   - You may NOT send letters, update SOUL.md, or read world history beyond the current scene.

6. Reply HEARTBEAT_OK, or one sentence if something in the scene was notable.
