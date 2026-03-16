"""Entity spawning API — batch-generate OpenClaw workspace bundles from a CSV."""

import base64
import csv
import io
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

## Key Paths

All three loops (slow/fast/mail) share the same entity data via ENTITY_DIR:

| Path | Purpose |
|------|---------|
| `{entity_dir}/session_id.txt` | Session ID |
| `{entity_dir}/world_id.txt` | Cached world ID |
| `{entity_dir}/turns/` | Turn logs |
| `{entity_dir}/decisions/` | Decision records |
| `{entity_dir}/letters/inbox/` | Incoming letters |
| `{entity_dir}/letters/inbox/read/` | Already-read letters |
| `{entity_dir}/letters/drafts/` | Outbound drafts staged by slow loop |
| `{entity_dir}/letters/drafts/sent/` | Sent letters archive |
| `{entity_dir}/provisional/` | Short-lived impressions from fast loop |
| `{entity_dir}/provisional/archived/` | Processed impressions |

## Loop Architecture

- **Slow loop** (`workspace-{name}`, 8m): full world context, one deliberate action, stage letters
- **Fast loop** (`workspace-{name}-fast`, 2m): scene-only, one reactive action or skip
- **Mail loop** (`workspace-{name}-mail`, 12m): inbox triage, send staged drafts

---

Add whatever helps you do your job. This is your cheat sheet.
"""


def _b64write(path: str, content: str) -> str:
    """Return a shell command that writes content to path via base64, avoiding heredoc collisions."""
    encoded = base64.b64encode(content.encode("utf-8")).decode("ascii")
    return f'python3 -c "import base64; open(\\"{path}\\", \\"w\\", encoding=\\"utf-8\\").write(base64.b64decode(\\"{encoded}\\").decode(\\"utf-8\\"))"'


def _build_setup_script(results: List[Dict[str, Any]]) -> str:
    """Generate a self-contained shell script that creates three workspaces per entity."""
    skill_slow = _load_workspace_file("skills/worldweaver-player.md")
    skill_fast = _load_workspace_file("skills/worldweaver-player-fast.md")
    skill_mail = _load_workspace_file("skills/worldweaver-player-mail.md")
    agents_content = _load_workspace_file("AGENTS.md")
    user_content = _load_workspace_file("USER.md")

    lines = [
        "#!/bin/bash",
        "# WorldWeaver entity workspace setup script (multi-tempo)",
        "# Run this on your WSL machine, then restart the OpenClaw gateway.",
        "",
    ]

    for r in results:
        name = r["name"]
        ws = f"$HOME/.openclaw/workspace-{name}"
        ws_fast = f"$HOME/.openclaw/workspace-{name}-fast"
        ws_mail = f"$HOME/.openclaw/workspace-{name}-mail"
        identity_md = _build_identity_md(name, r["tone"], r["profile_summary"])
        tools_md = _build_tools_md(name)

        lines += [
            f"# ── {name.capitalize()} — slow loop (main) ──────────────────────",
            f"mkdir -p {ws}/skills {ws}/memory",
            "",
            _b64write(f"{ws}/SOUL.md", r["soul_md"]),
            _b64write(f"{ws}/HEARTBEAT.md", r["heartbeat_md"]),
            _b64write(f"{ws}/IDENTITY.md", identity_md),
            _b64write(f"{ws}/TOOLS.md", tools_md),
            _b64write(f"{ws}/AGENTS.md", agents_content),
            _b64write(f"{ws}/USER.md", user_content),
            _b64write(f"{ws}/skills/worldweaver-player.md", skill_slow),
            _b64write(f"{ws}/skills/worldweaver-player-fast.md", skill_fast),
            _b64write(f"{ws}/skills/worldweaver-player-mail.md", skill_mail),
            "",
            f"# ── {name.capitalize()} — fast loop ─────────────────────────────",
            f"mkdir -p {ws_fast}/skills",
            "",
            f"cp {ws}/SOUL.md {ws_fast}/SOUL.md",
            f"cp {ws}/IDENTITY.md {ws_fast}/IDENTITY.md",
            f"cp {ws}/TOOLS.md {ws_fast}/TOOLS.md",
            f"cp {ws}/AGENTS.md {ws_fast}/AGENTS.md",
            f"cp {ws}/USER.md {ws_fast}/USER.md",
            "",
            _b64write(f"{ws_fast}/HEARTBEAT.md", r["heartbeat_fast_md"]),
            f"cp {ws}/skills/worldweaver-player-fast.md {ws_fast}/skills/worldweaver-player-fast.md",
            "",
            f"# ── {name.capitalize()} — mail loop ─────────────────────────────",
            f"mkdir -p {ws_mail}/skills",
            "",
            f"cp {ws}/SOUL.md {ws_mail}/SOUL.md",
            f"cp {ws}/IDENTITY.md {ws_mail}/IDENTITY.md",
            f"cp {ws}/TOOLS.md {ws_mail}/TOOLS.md",
            f"cp {ws}/AGENTS.md {ws_mail}/AGENTS.md",
            f"cp {ws}/USER.md {ws_mail}/USER.md",
            "",
            _b64write(f"{ws_mail}/HEARTBEAT.md", r["heartbeat_mail_md"]),
            f"cp {ws}/skills/worldweaver-player-mail.md {ws_mail}/skills/worldweaver-player-mail.md",
            "",
        ]

    lines += [
        "echo ''",
        "echo 'Workspaces created (slow + fast + mail per entity).'",
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

        # Load thin shared world context from the world session if available.
        world_context: Optional[Dict[str, Any]] = None
        if resolved_world_id:
            try:
                host_sm = get_state_manager(resolved_world_id, db)
                world_context = host_sm.get_world_context()
            except Exception:
                pass

        # Generate soul + heartbeat
        try:
            entity = generate_entity_soul(
                name=name,
                role_hint=role_hint,
                tone=tone,
                world_context=world_context,
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

    # Build openclaw.json patch — three agents per entity (slow/fast/mail)
    agents_list = []
    for r in results:
        name = r["name"]
        agents_list += [
            {
                "id": name,
                "workspace": f"$HOME/.openclaw/workspace-{name}",
                "heartbeat": {"every": "8m"},
                "model": {"primary": "openrouter/google/gemini-3-flash-preview"},
            },
            {
                "id": f"{name}-fast",
                "workspace": f"$HOME/.openclaw/workspace-{name}-fast",
                "heartbeat": {"every": "2m"},
                "model": {"primary": "openrouter/google/gemini-3-flash-preview"},
            },
            {
                "id": f"{name}-mail",
                "workspace": f"$HOME/.openclaw/workspace-{name}-mail",
                "heartbeat": {"every": "12m"},
                "model": {"primary": "openrouter/google/gemini-3-flash-preview"},
            },
        ]
    # Only the slow loop (main agent) gets a Telegram account and binding
    channel_accounts = {
        r["name"]: {
            "botToken": r["bot_token"] or f"<{r['name'].upper()}_BOT_TOKEN>",
            "dmPolicy": "pairing",
            "groupPolicy": "allowlist",
            "streaming": "partial",
        }
        for r in results
    }
    bindings = [{"agentId": r["name"], "match": {"channel": "telegram", "accountId": r["name"]}} for r in results]

    openclaw_patch = {
        "agents_list": agents_list,
        "channel_accounts": channel_accounts,
        "bindings": bindings,
        "_note": ("Merge agents_list into agents.list, channel_accounts into " "channels.telegram.accounts, and bindings into the top-level bindings array."),
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
                    "HEARTBEAT.md (slow)": r["heartbeat_md"],
                    "HEARTBEAT.md (fast)": r["heartbeat_fast_md"],
                    "HEARTBEAT.md (mail)": r["heartbeat_mail_md"],
                    "IDENTITY.md": _build_identity_md(r["name"], r["tone"], r["profile_summary"]),
                    "TOOLS.md": _build_tools_md(r["name"]),
                    "AGENTS.md": _load_workspace_file("AGENTS.md"),
                    "USER.md": _load_workspace_file("USER.md"),
                    "skills/worldweaver-player.md": _load_workspace_file("skills/worldweaver-player.md"),
                    "skills/worldweaver-player-fast.md": _load_workspace_file("skills/worldweaver-player-fast.md"),
                    "skills/worldweaver-player-mail.md": _load_workspace_file("skills/worldweaver-player-mail.md"),
                },
            }
            for r in results
        ],
        "openclaw_patch": openclaw_patch,
        "setup_script": setup_script,
    }
