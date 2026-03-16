"""
seed_world.py — Seed a normcore WorldWeaver world and optionally reset residents.

Calls:
    POST /api/dev/hard-reset   (optional — wipes all world data)
    POST /api/world/seed       (creates world_id + deterministic geography by default)

Then optionally resets all resident runtime state (session_id.txt, memory,
letters, decisions) so they start fresh in the new world.

Usage:
    python scripts/seed_world.py [OPTIONS]

    --server URL       WorldWeaver server URL (default: http://localhost:8000)
    --no-reset         Skip the hard-reset (add to an existing world instead)
    --no-residents     Skip resetting resident runtime state
    --residents-dir D  Path to residents directory (default: shard-local residents if resolvable)
    --theme TEXT       World theme override
    --tone TEXT        World tone override
    --count N          Number of storylets to generate (default: 20)
    --dry-run          Print payload without calling the server
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = ROOT.parent
SHARDS_ROOT = WORKSPACE_ROOT / "shards"


# ---------------------------------------------------------------------------
# Defaults — edit these to change the world without touching the CLI flags
# ---------------------------------------------------------------------------

DEFAULT_SERVER = "http://localhost:8000"

DEFAULT_PLAYER_ROLE = "A resident of the neighborhood, living an ordinary life."

DEFAULT_TONE = "quiet and observational; everyday life without manufactured drama"

DEFAULT_DESCRIPTION = (
    "A persistent, shared neighborhood where people live their lives. "
    "Characters walk to the park, grab coffee, run errands, sit on stoops. "
    "The world accumulates a quiet history through these small acts. "
    "Do not invent conflict or drama — let the texture of ordinary life be enough."
)

DEFAULT_STORYLET_COUNT = 5

# Per-city theme overrides — used when city-pack seeding is active and --theme is not explicitly set.
# The theme is injected into LLM enrichment prompts, so it should match the city being seeded.
CITY_THEMES: dict[str, str] = {
    "san_francisco": (
        "Everyday life in San Francisco's Mission District, grounded in real places — "
        "Dolores Park, taquerias, the BART, corner laundromats, weekend farmers markets."
    ),
    "portland": (
        "Everyday life in Portland, Oregon, grounded in real places — characters welcome. "
        "Powell's Books, food cart pods, the MAX light rail, neighborhood coffee shops, "
        "the Willamette River, and the quiet blocks of the inner eastside."
    ),
}

DEFAULT_THEME = CITY_THEMES["san_francisco"]


def _compose_cmd() -> list[str] | None:
    docker = shutil.which("docker")
    if docker:
        try:
            subprocess.call(
                [docker, "compose", "version"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return [docker, "compose"]
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# HTTP helpers (stdlib only — no httpx dependency here)
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=None) as resp:
        return json.loads(resp.read())


def _post_empty(url: str) -> dict:
    req = urllib.request.Request(url, data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


# ---------------------------------------------------------------------------
# Resident runtime reset
# ---------------------------------------------------------------------------

_RUNTIME_DIRS = ("memory", "letters", "decisions", "turns")
_RUNTIME_FILES = ("session_id.txt", "world_id.txt")


def _restore_entry_location(resident_dir: Path, dry_run: bool) -> None:
    """Re-write entry_location.txt from home_location in tuning.json.

    entry_location.txt is a one-time boot token consumed on first session start.
    After a world reset the token needs to be restored so the agent re-enters at
    their home location rather than the server default.
    """
    tuning_path = resident_dir / "identity" / "tuning.json"
    if not tuning_path.exists():
        return
    try:
        tuning = json.loads(tuning_path.read_text(encoding="utf-8"))
    except Exception:
        return
    home = tuning.get("home_location", "")
    if not home:
        return
    entry_path = resident_dir / "identity" / "entry_location.txt"
    print(f"  entry_location restore: {entry_path.relative_to(resident_dir.parent.parent)} → {home!r}")
    if not dry_run:
        entry_path.write_text(home, encoding="utf-8")


def _restore_soul(resident_dir: Path, dry_run: bool) -> None:
    """Truncate SOUL.md to canonical content (everything before the first '---' line)."""
    soul_path = resident_dir / "identity" / "SOUL.md"
    if not soul_path.exists():
        return
    text = soul_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    canonical: list[str] = []
    for line in lines:
        if line.rstrip() == "---":
            break
        canonical.append(line)
    restored = "".join(canonical).rstrip("\n") + "\n"
    if restored == text:
        return  # nothing to strip
    print(f"  soul restore: {soul_path.relative_to(resident_dir.parent.parent)}")
    if not dry_run:
        soul_path.write_text(restored, encoding="utf-8")


def _reset_resident(resident_dir: Path, dry_run: bool) -> None:
    name = resident_dir.name
    for d in _RUNTIME_DIRS:
        target = resident_dir / d
        if target.exists():
            print(f"  rm -rf {target.relative_to(resident_dir.parent.parent)}")
            if not dry_run:
                shutil.rmtree(target)
    for f in _RUNTIME_FILES:
        target = resident_dir / f
        if target.exists():
            print(f"  rm {target.relative_to(resident_dir.parent.parent)}")
            if not dry_run:
                target.unlink()
    _restore_soul(resident_dir, dry_run)
    _restore_entry_location(resident_dir, dry_run)
    print(f"  [ok] {name} reset")


def _reset_all_residents(residents_dir: Path, dry_run: bool) -> None:
    found = [
        d for d in residents_dir.iterdir()
        if d.is_dir() and not d.name.startswith("_") and (d / "identity" / "SOUL.md").exists()
    ]
    if not found:
        print("No residents found to reset.")
        return
    print(f"\nResetting {len(found)} resident(s):")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda d: _reset_resident(d, dry_run), sorted(found)))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _load_shard_env(shard_dir: Path) -> dict:
    """Read key=value pairs from a shard's .env file."""
    env_file = shard_dir / ".env"
    result: dict = {}
    if not env_file.exists():
        return result
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        result[k.strip()] = v.strip()
    return result


def _find_city_shard(city_id: str) -> Path | None:
    if not SHARDS_ROOT.exists():
        return None
    requested = str(city_id or "").strip().lower()
    for shard_dir in sorted(path for path in SHARDS_ROOT.iterdir() if path.is_dir()):
        env = _load_shard_env(shard_dir)
        if str(env.get("SHARD_TYPE") or "").strip().lower() == "world":
            continue
        if str(env.get("CITY_ID") or "").strip().lower() == requested:
            return shard_dir
    return None


def _stop_shard_agent(shard_dir: Path | None, dry_run: bool) -> None:
    compose = _compose_cmd()
    if not compose:
        print("      warning: docker compose unavailable — could not stop shard agent")
        return
    if shard_dir is None:
        print("      warning: no shard dir resolved — could not stop shard agent deterministically")
        return
    compose_file = shard_dir / "docker-compose.yml"
    if not compose_file.exists():
        print(f"      warning: shard compose file missing: {compose_file}")
        return
    cmd = [*compose, "-p", shard_dir.name, "-f", str(compose_file), "stop", "agent"]
    print(f"      {' '.join(cmd)}")
    if dry_run:
        return
    try:
        subprocess.run(cmd, check=True, capture_output=True, cwd=str(WORKSPACE_ROOT))
        print("      ok: shard agent stopped")
    except subprocess.CalledProcessError:
        print("      warning: could not stop shard agent (not running?)")


def _post_with_token(url: str, payload: dict, token: str | None) -> dict:
    """POST JSON with optional X-Federation-Token header."""
    data = json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Federation-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a normcore WorldWeaver world.")
    parser.add_argument("--server", default=DEFAULT_SERVER)
    parser.add_argument(
        "--shard-dir",
        default=None,
        help="Path to shard directory; reads .env to auto-configure --server and --city-id",
    )
    parser.add_argument("--no-reset", action="store_true", help="Skip hard-reset (keep existing world data)")
    parser.add_argument("--no-residents", action="store_true", help="Skip resetting resident runtime state")
    parser.add_argument("--residents-dir", default=None, help="Path to residents directory (default: auto-detected)")
    parser.add_argument("--theme", default=DEFAULT_THEME)
    parser.add_argument("--tone", default=DEFAULT_TONE)
    parser.add_argument("--count", type=int, default=DEFAULT_STORYLET_COUNT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--city-pack",
        action="store_true",
        help="Compatibility flag. City-pack seeding is now the default unless --llm-world is set.",
    )
    parser.add_argument(
        "--llm-world",
        action="store_true",
        help="Use legacy LLM-generated world locations instead of deterministic city-pack seeding.",
    )
    parser.add_argument(
        "--llm-city-pack",
        action="store_true",
        help="Enrich city-pack nodes with LLM-written descriptions during seeding.",
    )
    parser.add_argument(
        "--fast-city-pack",
        action="store_true",
        help="Compatibility alias for deterministic city-pack seeding without LLM enrichment.",
    )
    parser.add_argument("--city-id", default="san_francisco", help="City pack ID to use (default: san_francisco)")
    parser.add_argument("--federation-url", default=None, help="After seed, register shard with this federation root URL")
    parser.add_argument("--federation-token", default=None, help="Token for federation auth (X-Federation-Token)")
    args = parser.parse_args()

    shard_path: Path | None = None

    if args.fast_city_pack:
        args.city_pack = True
        args.llm_city_pack = False

    city_pack_mode = not args.llm_world

    # If --shard-dir provided, read .env and override server + city-id
    if args.shard_dir:
        shard_path = Path(args.shard_dir).resolve()
        if not shard_path.exists():
            print(f"ERROR: shard dir not found: {shard_path}", file=sys.stderr)
            sys.exit(1)
        shard_env = _load_shard_env(shard_path)
    else:
        shard_path = _find_city_shard(args.city_id)

    if shard_path is not None:
        shard_env = _load_shard_env(shard_path)
        if args.server == DEFAULT_SERVER and "BACKEND_PORT" in shard_env:
            args.server = f"http://localhost:{shard_env['BACKEND_PORT']}"
        if args.city_id == "san_francisco" and "CITY_ID" in shard_env:
            args.city_id = shard_env["CITY_ID"]
        if not args.federation_url and "FEDERATION_URL" in shard_env:
            args.federation_url = shard_env["FEDERATION_URL"]
        if not args.federation_token and "FEDERATION_TOKEN" in shard_env:
            args.federation_token = shard_env["FEDERATION_TOKEN"]
        if args.residents_dir is None:
            candidate = shard_path / "residents"
            if candidate.exists():
                args.residents_dir = str(candidate)

    # Default residents dir if still not set
    if args.residents_dir is None:
        args.residents_dir = str(ROOT.parent / "ww_agent" / "residents")

    # Resolve theme: if city-pack seeding is active and no explicit --theme, use the city-specific default.
    theme = args.theme
    if city_pack_mode and theme == DEFAULT_THEME and args.city_id in CITY_THEMES:
        theme = CITY_THEMES[args.city_id]

    server = args.server.rstrip("/")

    # 0. Stop agent service (city-pack seed is long-running and exhausts the DB pool)
    if city_pack_mode and not args.dry_run:
        print("[0/3] Stopping agent service to free DB connections during seeding...")
        _stop_shard_agent(shard_path, args.dry_run)

    # 1. Hard reset (or fetch existing world_id when adding to an existing world)
    existing_world_id = None
    if not args.no_reset:
        print(f"[1/3] Hard reset: POST {server}/api/dev/hard-reset")
        if not args.dry_run:
            try:
                result = _post_empty(f"{server}/api/dev/hard-reset")
                print(f"      ok: {result}")
            except urllib.error.HTTPError as e:
                body = e.read().decode()
                print(f"      ERROR {e.code}: {body}", file=sys.stderr)
                sys.exit(1)
        else:
            print("      [dry-run skipped]")
    else:
        print("[1/3] Skipping hard-reset (--no-reset)")
        if not args.dry_run:
            try:
                wid_result = _get(f"{server}/api/world/id")
                existing_world_id = wid_result.get("world_id") or None
                if existing_world_id:
                    print(f"      existing world_id: {existing_world_id}")
                else:
                    print("      no existing world found — will create a new one")
            except Exception as e:
                print(f"      warning: could not fetch existing world_id: {e}")

    # 2. Seed world
    seed_payload = {
        "world_theme": theme,
        "player_role": DEFAULT_PLAYER_ROLE,
        "description": DEFAULT_DESCRIPTION,
        "tone": args.tone,
        "storylet_count": args.count,
    }
    if city_pack_mode:
        seed_payload["seed_from_city_pack"] = True
        seed_payload["enrich_city_pack"] = bool(args.llm_city_pack)
        seed_payload["city_id"] = args.city_id
    else:
        seed_payload["seed_from_city_pack"] = False
    if existing_world_id:
        seed_payload["world_id"] = existing_world_id

    print(f"\n[2/3] Seed world: POST {server}/api/world/seed")
    if city_pack_mode:
        mode = "LLM enrichment enabled" if args.llm_city_pack else "deterministic default"
        print(f"      [city-pack mode] Using '{args.city_id}' city pack for location graph ({mode})")
    else:
        print("      [llm-world mode] Using legacy LLM-generated world locations")
    _skip_display = {"storylet_count"} if city_pack_mode else set()
    print("      payload:")
    for k, v in seed_payload.items():
        if k in _skip_display:
            continue
        short = v if len(str(v)) <= 80 else str(v)[:77] + "..."
        print(f"        {k}: {short}")

    world_id = None
    if not args.dry_run:
        try:
            result = _post(f"{server}/api/world/seed", seed_payload)
            world_id = result.get("world_id")
            storylet_count = result.get("storylet_count", "?")
            nodes_seeded = result.get("nodes_seeded", None)
            city_pack_used = result.get("city_pack_used", None)
            summary = f"world_id={world_id}  storylets={storylet_count}"
            if nodes_seeded is not None:
                summary += f"  nodes={nodes_seeded}  city_pack={city_pack_used}"
            print(f"      ok: {summary}")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"      ERROR {e.code}: {body}", file=sys.stderr)
            sys.exit(1)
    else:
        print("      [dry-run skipped]")

    # 2b. Register with federation root (if --federation-url provided)
    if args.federation_url and not args.dry_run:
        fed_url = args.federation_url.rstrip("/")
        print(f"\n[2b] Register shard: POST {fed_url}/api/federation/register")
        reg_payload = {
            "shard_id": args.city_id,
            "shard_url": server,
            "shard_type": "city",
            "city_id": args.city_id,
        }
        try:
            reg_result = _post_with_token(
                f"{fed_url}/api/federation/register",
                reg_payload,
                args.federation_token,
            )
            print(f"      ok: {reg_result}")
        except urllib.error.HTTPError as e:
            body = e.read().decode()
            print(f"      WARNING: federation register failed {e.code}: {body}", file=sys.stderr)
        except Exception as e:
            print(f"      WARNING: federation register failed: {e}", file=sys.stderr)
    elif args.federation_url and args.dry_run:
        print(f"\n[2b] [dry-run] Would register shard with {args.federation_url}")

    # 3. Reset residents
    residents_dir = Path(args.residents_dir)
    if not args.no_residents:
        if residents_dir.exists():
            _reset_all_residents(residents_dir, args.dry_run)
        else:
            print(f"\n[3/3] Residents dir not found: {residents_dir} — skipping")
    else:
        print("\n[3/3] Skipping resident reset (--no-residents)")

    print("\nDone. World is ready.")
    if world_id:
        print(f"  world_id: {world_id}")
    if args.city_pack and not args.dry_run:
        print("  Run: docker compose start agent   (to boot residents into the new world)")
    else:
        print("  Start ww_agent to boot residents into the new world.")


if __name__ == "__main__":
    main()
