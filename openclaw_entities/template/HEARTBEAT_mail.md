# HEARTBEAT.md — {NAME} (Mail Loop)

## Artifact Root

```bash
ENTITY_DIR={ENTITY_DIR}
AGENT_NAME="{NAME_LOWER}"
```

---

## Mail Loop Check-in

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

4. Read and archive the inbox:
   ```bash
   mkdir -p $ENTITY_DIR/letters/inbox/read
   for letter in $ENTITY_DIR/letters/inbox/*.md; do
     [ -f "$letter" ] || continue
     echo "=== $(basename $letter) ==="
     cat "$letter"
     echo "---"
     mv "$letter" $ENTITY_DIR/letters/inbox/read/
   done
   ```
   For each letter: decide if it warrants a reply. Check for a `Reply-To-Session:` header.

5. Send at most one reply this cycle (only if a letter genuinely warrants one):
   ```bash
   curl -s -X POST http://localhost:8000/api/world/letter/reply \
     -H "Content-Type: application/json" \
     -d "{
       \"from_agent\": \"$AGENT_NAME\",
       \"to_session_id\": \"REPLY_SESSION_ID_HERE\",
       \"body\": \"YOUR REPLY HERE\"
     }"
   ```
   Write the reply in character as {NAME}. Under 400 words.

6. Check staged drafts from the slow loop:
   ```bash
   for draft in $ENTITY_DIR/letters/drafts/*.md; do
     [ -f "$draft" ] || continue
     cat "$draft"
     echo "---"
   done
   ```
   For each draft: read the `Urgency:` field. Decide to send, hold, or discard.

7. Send at most one outbound letter this cycle (the most urgent draft):
   ```bash
   mkdir -p $ENTITY_DIR/letters/drafts/sent
   curl -s -X POST http://localhost:8000/api/world/letter \
     -H "Content-Type: application/json" \
     -d "{
       \"to_agent\": \"RECIPIENT_HERE\",
       \"from_name\": \"$AGENT_NAME\",
       \"body\": \"BODY_HERE\",
       \"session_id\": \"$SESSION_ID\"
     }"
   ```
   Move the sent draft: `mv "$draft" $ENTITY_DIR/letters/drafts/sent/`
   Exception: also send any draft with `Urgency: urgent`.

8. Reply HEARTBEAT_OK. If you sent a letter, say who you wrote to.
