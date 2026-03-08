"""Entity spawning API — batch-generate OpenClaw workspace bundles from a CSV."""

import csv
import io
import json
import logging
import textwrap
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.session_service import get_state_manager
from ...services.llm_service import generate_entity_soul

router = APIRouter()
logger = logging.getLogger(__name__)

# CSV columns (name and role_hint required; rest optional)
_REQUIRED_COLS = {"name", "role_hint"}
_OPTIONAL_COLS = {"bot_token", "tone", "world_id"}

# Shared workspace files every entity needs (copied from existing workspace)
_SHARED_FILES = ["AGENTS.md", "IDENTITY.md", "TOOLS.md", "USER.md"]


def _parse_csv(content: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content.strip()))
    rows = []
    for i, row in enumerate(reader):
        missing = _REQUIRED_COLS - set(row.keys())
        if missing:
            raise ValueError(f"CSV row {i + 1} missing columns: {missing}")
        rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def _build_bootstrap_payload(
    entity: Dict[str, Any],
    world_id: Optional[str],
    is_founder: bool,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "session_id": f"$SESSION_ID",
        "world_theme": "cozy neighborhood slice-of-life",
        "player_role": entity["player_role"],
        "tone": entity["tone"],
        "key_elements": entity.get("key_elements", []),
        "storylet_count": 8,
        "bootstrap_source": "openclaw-agent",
    }
    if entity.get("bootstrap_description"):
        payload["description"] = entity["bootstrap_description"]
    if not is_founder and world_id:
        payload["world_id"] = world_id
    return payload


def _bootstrap_curl(payload: Dict[str, Any], founder_name: Optional[str], is_founder: bool) -> str:
    """Render the bootstrap curl command for a HEARTBEAT setup section."""
    payload_copy = dict(payload)
    payload_copy["session_id"] = "$SESSION_ID"
    if not is_founder and founder_name:
        payload_copy["world_id"] = f"$(cat ~/worldweaver_runs/{founder_name}/session_id.txt)"

    lines = ["curl -s -X POST http://localhost:8000/api/session/bootstrap \\"]
    lines.append('  -H "Content-Type: application/json" \\')
    lines.append("  -d '{")
    items = list(payload_copy.items())
    for j, (k, v) in enumerate(items):
        comma = "," if j < len(items) - 1 else ""
        if isinstance(v, list):
            lines.append(f'    "{k}": {json.dumps(v)}{comma}')
        elif isinstance(v, str) and v.startswith("$"):
            lines.append(f'    "{k}": "\'${{{v[1:]}}}\'"' + comma if False else f'    "{k}": "' + v + '"' + comma)
        else:
            lines.append(f'    "{k}": {json.dumps(v)}{comma}')
    lines.append("  }'")
    return "\n".join(lines)


def _build_setup_script(results: List[Dict[str, Any]], world_id_map: Dict[str, str]) -> str:
    """Generate a shell script that creates all workspaces and writes all entity files."""
    lines = [
        "#!/bin/bash",
        "# WorldWeaver entity workspace setup script",
        "# Run this on your WSL machine, then restart the OpenClaw gateway.",
        "",
        'SKILL_SRC="$HOME/.openclaw/workspace/skills/worldweaver-player.md"',
        "",
    ]

    for r in results:
        name = r["name"]
        ws = f"$HOME/.openclaw/workspace-{name}"
        lines += [
            f"# ── {name.capitalize()} ──────────────────────────────────────────",
            f"mkdir -p {ws}/skills",
            f'cat > {ws}/SOUL.md << \'SOUL_EOF\'',
            r["soul_md"].rstrip(),
            "SOUL_EOF",
            "",
            f'cat > {ws}/HEARTBEAT.md << \'HB_EOF\'',
            r["heartbeat_md"].rstrip(),
            "HB_EOF",
            "",
            f'cp "$SKILL_SRC" {ws}/skills/worldweaver-player.md',
            f'for f in AGENTS.md IDENTITY.md TOOLS.md USER.md; do',
            f'  [ -f "$HOME/.openclaw/workspace/$f" ] && cp "$HOME/.openclaw/workspace/$f" {ws}/$f',
            f'done',
            "",
        ]

    lines += [
        "echo 'Workspaces created. Add the openclaw_patch entries to your openclaw.json and restart the gateway.'",
        "",
    ]
    return "\n".join(lines)


@router.post("/entities/spawn-batch")
async def spawn_entity_batch(
    file: UploadFile = File(...),
    world_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
):
    """Spawn one or more OpenClaw entities from a CSV file.

    CSV columns:
      - name        (required) entity slug, e.g. "elian"
      - role_hint   (required) brief character description
      - bot_token   (optional) Telegram bot token for this entity
      - tone        (optional) narrative tone, defaults to "warm, observant"
      - world_id    (optional) session_id of the world founder to join;
                    leave blank for the founder row itself

    The first row with no world_id is treated as the founder.
    Subsequent rows with no world_id will be assigned the founder's name.

    Returns generated SOUL.md + HEARTBEAT.md per entity, an openclaw.json patch,
    and a shell setup script to run on WSL.
    """
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded.")

    try:
        rows = _parse_csv(content)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if not rows:
        raise HTTPException(status_code=422, detail="CSV has no data rows.")

    # Determine founder: first row with no world_id column value (or explicit world_id param)
    founder_name: Optional[str] = None
    founder_world_id: Optional[str] = world_id  # override from form param

    results: List[Dict[str, Any]] = []
    existing_entities: List[Dict[str, str]] = []
    world_id_map: Dict[str, str] = {}  # name -> resolved world_id

    for i, row in enumerate(rows):
        name = row["name"].lower()
        role_hint = row["role_hint"]
        tone = row.get("tone") or "warm, observant"
        bot_token = row.get("bot_token") or ""
        row_world_id = row.get("world_id") or founder_world_id or ""

        is_founder = not row_world_id and founder_name is None

        # Resolve which world this entity joins
        if is_founder:
            founder_name = name
            resolved_world_id = None  # founder has no world_id
        elif row_world_id:
            resolved_world_id = row_world_id
        elif founder_name:
            resolved_world_id = founder_name  # symbolic — setup script uses file path
        else:
            resolved_world_id = None

        world_id_map[name] = resolved_world_id or ""

        # Load world bible from resolved world if available
        world_bible: Optional[Dict[str, Any]] = None
        if resolved_world_id:
            try:
                host_sm = get_state_manager(resolved_world_id, db)
                world_bible = host_sm.get_world_bible()
            except Exception:
                pass
        elif founder_name and results:
            # Founder may not have bootstrapped yet — world bible not available
            pass

        # Generate soul
        try:
            entity = generate_entity_soul(
                name=name,
                role_hint=role_hint,
                tone=tone,
                world_bible=world_bible,
                existing_entities=existing_entities,
            )
        except Exception as exc:
            logger.error("Entity soul generation failed for %s: %s", name, exc)
            raise HTTPException(status_code=500, detail=f"Generation failed for '{name}': {exc}")

        entity["bot_token"] = bot_token
        entity["is_founder"] = is_founder
        entity["resolved_world_id"] = resolved_world_id

        results.append(entity)
        existing_entities.append({"name": name, "summary": entity["profile_summary"]})

    # Build openclaw.json patch
    agents_list = [
        {
            "id": r["name"],
            **({"default": True} if r["is_founder"] else {}),
            "workspace": f"/home/$USER/.openclaw/workspace-{r['name']}",
        }
        for r in results
    ]
    channel_accounts = {
        r["name"]: {
            "botToken": r["bot_token"] or f"<{r['name'].upper()}_BOT_TOKEN>",
            "dmPolicy": "pairing",
            "groupPolicy": "allowlist",
            "streaming": "partial",
        }
        for r in results
    }
    bindings = [
        {"agentId": r["name"], "match": {"channel": "telegram", "accountId": r["name"]}}
        for r in results
    ]

    openclaw_patch = {
        "agents_list": agents_list,
        "channel_accounts": channel_accounts,
        "bindings": bindings,
        "_note": (
            "Merge agents_list into agents.list, channel_accounts into "
            "channels.telegram.accounts, and bindings into the top-level bindings array."
        ),
    }

    setup_script = _build_setup_script(results, world_id_map)

    return {
        "entity_count": len(results),
        "entities": [
            {
                "name": r["name"],
                "role": "founder" if r["is_founder"] else "resident",
                "world_id": r["resolved_world_id"],
                "player_role": r["player_role"],
                "profile_summary": r["profile_summary"],
                "soul_md": r["soul_md"],
                "heartbeat_md": r["heartbeat_md"],
            }
            for r in results
        ],
        "openclaw_patch": openclaw_patch,
        "setup_script": setup_script,
    }
