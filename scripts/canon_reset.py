#!/usr/bin/env python3
"""
canon_reset.py — Prune non-canon world drift and reset resident runtime state.

Preserves all city-pack seeded WorldNode/WorldEdge records (source=city_pack).
Removes nodes introduced by LLM narration, player travel, or world bootstrap.
Clears all WorldEvents and WorldFacts to reset the timeline (pass --keep-events
to preserve history).  Resets resident runtime state so agents boot fresh.

Does NOT re-seed the world.  City-pack geography remains intact.

Usage:
    python scripts/canon_reset.py [OPTIONS]

    --db-url URL        SQLAlchemy DB URL (default: DATABASE_URL env or worldweaver.db)
    --residents-dir D   Path to ww_agent residents directory
                        (default: ../ww_agent/residents)
    --no-residents      Skip resident runtime reset
    --keep-events       Do not delete WorldEvent/WorldFact rows (keeps history)
    --rebuild           Stop agent, prune, reset residents, then do a full
                        stack-down + stack-up --build (convenience wrapper)
    --dry-run           Print what would change without modifying anything

Examples:
    # Full reset — prune drift, clear events, reset agents:
    python scripts/canon_reset.py

    # Full reset + rebuild the whole stack:
    python scripts/canon_reset.py --rebuild

    # Keep event history, only prune nodes and reset agents:
    python scripts/canon_reset.py --keep-events

    # Preview without changing anything:
    python scripts/canon_reset.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESIDENTS_DIR = ROOT.parent / "ww_agent" / "residents"

_RUNTIME_DIRS = ("memory", "letters", "decisions", "turns")
_RUNTIME_FILES = ("session_id.txt", "world_id.txt")


# ---------------------------------------------------------------------------
# Docker / compose helpers
# ---------------------------------------------------------------------------


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


def _docker_stop_agent(dry_run: bool) -> None:
    cmd = _compose_cmd()
    if not cmd:
        print("  warning: docker compose unavailable — skipping agent stop")
        return
    print("  docker compose stop agent")
    if not dry_run:
        try:
            subprocess.run([*cmd, "stop", "agent"], check=True, capture_output=True, cwd=str(ROOT))
            print("  ok: agent stopped")
        except subprocess.CalledProcessError:
            print("  warning: could not stop agent (not running?)")


def _docker_stack_down(dry_run: bool) -> None:
    cmd = _compose_cmd()
    if not cmd:
        print("  warning: docker compose unavailable — skipping stack-down")
        return
    print("  docker compose down --remove-orphans")
    if not dry_run:
        subprocess.run([*cmd, "down", "--remove-orphans"], cwd=str(ROOT))


def _docker_stack_up_build(dry_run: bool) -> None:
    cmd = _compose_cmd()
    if not cmd:
        print("  warning: docker compose unavailable — skipping stack-up")
        return
    print("  docker compose up -d --build")
    if not dry_run:
        subprocess.run([*cmd, "up", "-d", "--build"], cwd=str(ROOT))


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _resolve_db_url(override: str | None) -> str | None:
    if override:
        return override
    # DW_DB_PATH mirrors what database.py + docker-compose use
    dw = os.environ.get("DW_DB_PATH", "").strip()
    if dw:
        return f"sqlite:///{dw}"
    env = os.environ.get("DATABASE_URL", "").strip()
    if env:
        return env
    for rel in ("worldweaver.db", "db/worldweaver.db"):
        candidate = ROOT / rel
        if candidate.exists():
            return f"sqlite:///{candidate}"
    return None


def _canon_prune(db_url: str, *, keep_events: bool, dry_run: bool) -> dict:
    """Delete non-canon graph nodes and optionally wipe events/facts.

    Canon = WorldNode rows where metadata_json['source'] == 'city_pack'.
    Non-canon = anything else (world_bible, player_travel, narration drift).
    """
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
    except ImportError:
        print("ERROR: sqlalchemy not installed.  Run: pip install sqlalchemy")
        sys.exit(1)

    sys.path.insert(0, str(ROOT))
    from src.models import WorldEdge, WorldEvent, WorldFact, WorldNode

    kwargs = {"check_same_thread": False} if "sqlite" in db_url else {}
    engine = create_engine(db_url, connect_args=kwargs)
    Session = sessionmaker(bind=engine)

    result = {
        "nodes_kept": 0,
        "nodes_deleted": 0,
        "edges_deleted": 0,
        "facts_deleted": 0,
        "events_deleted": 0,
    }

    with Session() as session:
        all_nodes = session.query(WorldNode).all()

        keep_ids: set[int] = set()
        delete_ids: set[int] = set()
        delete_names: list[str] = []

        for n in all_nodes:
            meta = n.metadata_json or {}
            if meta.get("source") == "city_pack":
                keep_ids.add(int(n.id))
                result["nodes_kept"] += 1
            else:
                delete_ids.add(int(n.id))
                delete_names.append(f"{n.node_type}:{n.name}")

        print(f"  WorldNodes: {result['nodes_kept']} canon (keep), {len(delete_ids)} non-canon (delete)")
        if delete_names[:10]:
            sample = ", ".join(delete_names[:8])
            suffix = f"… (+{len(delete_names) - 8} more)" if len(delete_names) > 8 else ""
            print(f"    sample: {sample}{suffix}")

        if delete_ids:
            edges_q = session.query(WorldEdge).filter(WorldEdge.source_node_id.in_(delete_ids) | WorldEdge.target_node_id.in_(delete_ids))
            edge_count = edges_q.count()
            print(f"  WorldEdges touching deleted nodes: {edge_count}")

            facts_q = session.query(WorldFact).filter(WorldFact.subject_node_id.in_(delete_ids) | WorldFact.location_node_id.in_(delete_ids))
            fact_count = facts_q.count()
            print(f"  WorldFacts touching deleted nodes: {fact_count}")

            if not dry_run:
                edges_q.delete(synchronize_session=False)
                result["edges_deleted"] = edge_count
                facts_q.delete(synchronize_session=False)
                result["facts_deleted"] = fact_count
                session.query(WorldNode).filter(WorldNode.id.in_(delete_ids)).delete(synchronize_session=False)
                result["nodes_deleted"] = len(delete_ids)
                session.flush()

        if not keep_events:
            ev_count = session.query(WorldEvent).count()
            fa_count = session.query(WorldFact).count()  # remaining after node prune
            print(f"  WorldEvents to clear: {ev_count}")
            print(f"  WorldFacts remaining to clear: {fa_count}")
            if not dry_run:
                session.query(WorldEvent).delete(synchronize_session=False)
                session.query(WorldFact).delete(synchronize_session=False)
                result["events_deleted"] = ev_count
                result["facts_deleted"] += fa_count

        if not dry_run:
            session.commit()

    return result


# ---------------------------------------------------------------------------
# Resident reset (mirrors ww_agent/scripts/seed_world.py)
# ---------------------------------------------------------------------------


def _restore_soul(resident_dir: Path, dry_run: bool) -> None:
    """Truncate SOUL.md to canonical content (everything before first '---')."""
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
        return
    rel = soul_path.relative_to(resident_dir.parent.parent)
    print(f"    soul restore: {rel}")
    if not dry_run:
        soul_path.write_text(restored, encoding="utf-8")


def _reset_resident(resident_dir: Path, dry_run: bool) -> None:
    name = resident_dir.name
    for d in _RUNTIME_DIRS:
        target = resident_dir / d
        if target.exists():
            rel = target.relative_to(resident_dir.parent.parent)
            print(f"    rm -rf {rel}")
            if not dry_run:
                shutil.rmtree(target)
    for f in _RUNTIME_FILES:
        target = resident_dir / f
        if target.exists():
            rel = target.relative_to(resident_dir.parent.parent)
            print(f"    rm {rel}")
            if not dry_run:
                target.unlink()
    _restore_soul(resident_dir, dry_run)
    print(f"    [ok] {name}")


def _reset_residents(residents_dir: Path, dry_run: bool) -> None:
    found = [d for d in residents_dir.iterdir() if d.is_dir() and not d.name.startswith("_") and (d / "identity" / "SOUL.md").exists()]
    if not found:
        print("  No residents found to reset.")
        return
    print(f"  Resetting {len(found)} resident(s):")
    for resident_dir in sorted(found):
        _reset_resident(resident_dir, dry_run)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prune non-canon world drift and reset residents (no re-seed).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db-url", default=None, help="SQLAlchemy DB URL")
    parser.add_argument(
        "--residents-dir",
        default=str(DEFAULT_RESIDENTS_DIR),
        help=f"ww_agent residents directory (default: {DEFAULT_RESIDENTS_DIR})",
    )
    parser.add_argument("--no-residents", action="store_true", help="Skip resident reset")
    parser.add_argument(
        "--keep-events",
        action="store_true",
        help="Preserve WorldEvent/WorldFact history (only prune drift nodes)",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Stop agent, prune, reset residents, then stack-down + stack-up --build",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without modifying")
    args = parser.parse_args()

    if args.dry_run:
        print("[dry-run] No changes will be made.\n")

    total_steps = 4 if args.rebuild else 2

    # ── Step 0 (--rebuild): stop agent service ────────────────────────────────
    if args.rebuild:
        print(f"[0/{total_steps}] Stopping agent service")
        _docker_stop_agent(args.dry_run)

    # ── Step 1: prune non-canon nodes ────────────────────────────────────────
    db_url = _resolve_db_url(args.db_url)
    if not db_url:
        print("ERROR: No database found.  Set DATABASE_URL env var or ensure worldweaver.db exists.")
        return 1

    print(f"[1/{total_steps}] Pruning non-canon nodes")
    print(f"      db: {db_url}")
    if args.keep_events:
        print("      (--keep-events: WorldEvent/WorldFact history preserved)")
    try:
        counts = _canon_prune(db_url, keep_events=args.keep_events, dry_run=args.dry_run)
    except Exception as exc:
        print(f"ERROR during DB prune: {exc}")
        return 1

    if not args.dry_run:
        print(f"  Deleted: {counts['nodes_deleted']} nodes, {counts['edges_deleted']} edges, " f"{counts['facts_deleted']} facts, {counts['events_deleted']} events")

    # ── Step 2: reset residents ───────────────────────────────────────────────
    residents_dir = Path(args.residents_dir)
    if not args.no_residents:
        print(f"\n[2/{total_steps}] Resetting residents")
        print(f"      dir: {residents_dir}")
        if residents_dir.exists():
            _reset_residents(residents_dir, args.dry_run)
        else:
            print("  Residents dir not found — skipping")
    else:
        print(f"\n[2/{total_steps}] Skipping resident reset (--no-residents)")

    # ── Steps 3–4 (--rebuild): stack-down + stack-up --build ─────────────────
    if args.rebuild:
        print(f"\n[3/{total_steps}] Stack down")
        _docker_stack_down(args.dry_run)

        print(f"\n[4/{total_steps}] Stack up --build")
        _docker_stack_up_build(args.dry_run)

    suffix = "  (dry-run — nothing was changed)" if args.dry_run else ""
    print(f"\nDone.{suffix}")
    if not args.dry_run:
        if args.rebuild:
            print("  City-pack geography intact.  Stack is coming up fresh.")
        else:
            print("  City-pack geography intact.  Start agents to reboot residents.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
