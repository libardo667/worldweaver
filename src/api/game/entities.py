"""Entity spawning API — batch-generate OpenClaw workspace bundles from a CSV."""

import csv
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.session_service import get_state_manager
from ...services.llm_service import generate_entity_soul

router = APIRouter()
logger = logging.getLogger(__name__)

_OPENCLAW_ENTITIES = Path(__file__).parent.parent.parent.parent / "openclaw_entities"

# Files loaded from the canonical entity folder and embedded inline in setup scripts
def _load_workspace_file(filename: str) -> str:
    path = _OPENCLAW_ENTITIES / "template" / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning("Workspace file not found: %s", path)
        return f"# {filename}\n\n(file not found at build time)\n"

# CSV columns (name and role_hint required; rest optional)
_REQUIRED_COLS = {"name", "role_hint"}
_OPTIONAL_COLS = {"bot_token", "tone", "world_id"}


def _parse_csv(content: str) -> List[Dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content.strip()))
    rows = []
    for i, row in enumerate(reader):
        missing = _REQUIRED_COLS - set(row.keys())
        if missing:
            raise ValueError(f"CSV row {i + 1} missing columns: {missing}")
        rows.append({k: (v or "").strip() for k, v in row.items()})
    return rows


def _build_identity_md(name: str, tone: str, profile_summary: str) -> str:
    n = name.capitalize()
    return f"""# IDENTITY.md — {n}

- **Name:** {n}
- **Creature:** WorldWeaver resident
- **Vibe:** {tone}
- **Emoji:**
- **Avatar:**

---

{profile_summary}
"""


def _build_tools_md(name: str) -> str:
    n = name.capitalize()
    ws = f"$HOME/.openclaw/workspace-{name}"
    entity_dir = f"{ws}/worldweaver_runs/{name}"
    return f"""# TOOLS.md — {n}'s Toolkit

## WorldWeaver Server

- URL: `http://localhost:8000`
- API base: `http://localhost:8000/api`
- Health: `curl -s http://localhost:8000/health`
- World ID: `curl -s http://localhost:8000/api/world/id`
- Skill reference: `{ws}/skills/worldweaver-player.md`

## Key Paths

| Path | Purpose |
|------|---------|
| `{entity_dir}/world_id.txt` | Cached world ID (fetched once from GET /api/world/id on first setup) |
| `{entity_dir}/turns/` | Turn logs |
| `{entity_dir}/decisions/` | Decision records |
| `{entity_dir}/letters/` | Penpal letters |
| `{entity_dir}/letters/inbox/` | Incoming player letters |
| `{entity_dir}/letters/inbox/read/` | Already-read letters |
| `{entity_dir}/session_id.txt` | Session ID |

---

Add whatever helps you do your job. This is your cheat sheet.
"""


def _build_setup_script(results: List[Dict[str, Any]]) -> str:
    """Generate a self-contained shell script that creates all workspaces with all 6 required files."""
    skill_content = _load_workspace_file("skills/worldweaver-player.md")
    agents_content = _load_workspace_file("AGENTS.md")
    user_content = _load_workspace_file("USER.md")

    lines = [
        "#!/bin/bash",
        "# WorldWeaver entity workspace setup script",
        "# Run this on your WSL machine, then restart the OpenClaw gateway.",
        "",
    ]

    for r in results:
        name = r["name"]
        ws = f"$HOME/.openclaw/workspace-{name}"
        identity_md = _build_identity_md(name, r["tone"], r["profile_summary"])
        tools_md = _build_tools_md(name)

        lines += [
            f"# ── {name.capitalize()} ──────────────────────────────────────────",
            f"mkdir -p {ws}/skills {ws}/memory",
            "",
            f"cat > {ws}/SOUL.md << 'SOUL_EOF'",
            r["soul_md"].rstrip(),
            "SOUL_EOF",
            "",
            f"cat > {ws}/HEARTBEAT.md << 'HB_EOF'",
            r["heartbeat_md"].rstrip(),
            "HB_EOF",
            "",
            f"cat > {ws}/IDENTITY.md << 'ID_EOF'",
            identity_md.rstrip(),
            "ID_EOF",
            "",
            f"cat > {ws}/TOOLS.md << 'TOOLS_EOF'",
            tools_md.rstrip(),
            "TOOLS_EOF",
            "",
            f"cat > {ws}/AGENTS.md << 'AGENTS_EOF'",
            agents_content.rstrip(),
            "AGENTS_EOF",
            "",
            f"cat > {ws}/USER.md << 'USER_EOF'",
            user_content.rstrip(),
            "USER_EOF",
            "",
            f"cat > {ws}/skills/worldweaver-player.md << 'SKILL_EOF'",
            skill_content.rstrip(),
            "SKILL_EOF",
            "",
        ]

    lines += [
        "echo ''",
        "echo 'Workspaces created.'",
        "echo 'Next: merge the openclaw_patch into your ~/.openclaw/openclaw.json and restart the gateway.'",
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
      - name        (required) entity slug, e.g. "nadia"
      - role_hint   (required) brief character description
      - bot_token   (optional) Telegram bot token for this entity
      - tone        (optional) narrative tone, defaults to "warm, observant"
      - world_id    (optional) per-row world override; falls back to the form param

    All entities are residents. There is no founder. Seed the world first via
    POST /api/world/seed, then pass the returned world_id as the form param.

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

    results: List[Dict[str, Any]] = []
    existing_entities: List[Dict[str, str]] = []

    for row in rows:
        name = row["name"].lower()
        role_hint = row["role_hint"]
        tone = row.get("tone") or "warm, observant"
        bot_token = row.get("bot_token") or ""
        resolved_world_id = row.get("world_id") or world_id or None

        # Load world bible from the world session if available
        world_bible: Optional[Dict[str, Any]] = None
        if resolved_world_id:
            try:
                host_sm = get_state_manager(resolved_world_id, db)
                world_bible = host_sm.get_world_bible()
            except Exception:
                pass

        # Generate soul + heartbeat
        try:
            entity = generate_entity_soul(
                name=name,
                role_hint=role_hint,
                tone=tone,
                world_bible=world_bible,
                existing_entities=existing_entities,
                resolved_world_id=resolved_world_id,
            )
        except Exception as exc:
            logger.error("Entity soul generation failed for %s: %s", name, exc)
            raise HTTPException(status_code=500, detail=f"Generation failed for '{name}': {exc}")

        entity["bot_token"] = bot_token
        entity["resolved_world_id"] = resolved_world_id

        results.append(entity)
        existing_entities.append({"name": name, "summary": entity["profile_summary"]})

    # Build openclaw.json patch — include heartbeat so agents fire without a manual poke
    agents_list = [
        {
            "id": r["name"],
            "workspace": f"$HOME/.openclaw/workspace-{r['name']}",
            "heartbeat": {"every": "5m"},
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

    setup_script = _build_setup_script(results)

    return {
        "entity_count": len(results),
        "entities": [
            {
                "name": r["name"],
                "role": "resident",
                "world_id": r["resolved_world_id"],
                "player_role": r["player_role"],
                "profile_summary": r["profile_summary"],
                "files": {
                    "SOUL.md": r["soul_md"],
                    "HEARTBEAT.md": r["heartbeat_md"],
                    "IDENTITY.md": _build_identity_md(r["name"], r["tone"], r["profile_summary"]),
                    "TOOLS.md": _build_tools_md(r["name"]),
                    "AGENTS.md": _load_workspace_file("AGENTS.md"),
                    "USER.md": _load_workspace_file("USER.md"),
                    "skills/worldweaver-player.md": _load_workspace_file("skills/worldweaver-player.md"),
                },
            }
            for r in results
        ],
        "openclaw_patch": openclaw_patch,
        "setup_script": setup_script,
    }
