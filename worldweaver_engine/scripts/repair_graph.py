#!/usr/bin/env python3
"""
repair_graph.py — Connect orphan location nodes and landmarks to the path graph.

Two classes of disconnected node are fixed:

  1. Orphan location nodes — city-pack neighborhoods/districts with no path
     edges at all (caused by sparse or missing adjacent_to data in the pack).
     Fixed by connecting each to its K nearest non-orphan location nodes.

  2. Landmark nodes — real SF places (museums, parks, buildings…) that are
     seeded from the city pack but never get path edges because the pack only
     encodes neighborhood adjacency.  Fixed by connecting each landmark to its
     K nearest city-pack location nodes.  This makes landmarks discoverable via
     natural language ("walk to City Hall") without inventing fake locations.

Usage:
    python scripts/repair_graph.py [OPTIONS]

    --db-url URL     SQLAlchemy DB URL (default: shard WW_DB_* / WW_DATABASE_URL,
                     then DATABASE_URL, then sqlite compatibility fallback)
    --k N            Number of neighbors to connect each orphan to (default: 2)
    --max-km FLOAT   Max connection distance in km (default: 5.0)
    --dry-run        Print what would change without modifying anything

Examples:
    python scripts/repair_graph.py
    python scripts/repair_graph.py --k 3 --max-km 3.0
    python scripts/repair_graph.py --dry-run
"""

from __future__ import annotations

import argparse
import math
import os
import sys
from pathlib import Path
from urllib.parse import quote_plus

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Haversine distance
# ---------------------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(
        math.radians(lat2)
    ) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(max(0.0, min(1.0, a))))


def _load_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _normalize_database_url(url: str) -> str:
    normalized = str(url or "").strip()
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+psycopg://", 1)
    return normalized


def _compose_postgres_url(env: dict[str, str]) -> str:
    host = str(env.get("WW_DB_HOST") or "").strip()
    name = str(env.get("WW_DB_NAME") or "").strip()
    if not host or not name:
        return ""

    user = str(env.get("WW_DB_USER") or "postgres").strip() or "postgres"
    password = str(env.get("WW_DB_PASSWORD") or "postgres")
    port = str(env.get("WW_DB_PORT") or "5432").strip() or "5432"
    return (
        "postgresql+psycopg://"
        f"{quote_plus(user)}:{quote_plus(password)}@{host}:{port}/{quote_plus(name)}"
    )


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _resolve_db_url(override: str | None, shard_dir: Path | None = None) -> str | None:
    if override:
        return _normalize_database_url(override)
    if shard_dir is not None:
        shard_env = _load_env_file(shard_dir / ".env")
        component_url = _compose_postgres_url(shard_env)
        if component_url:
            return component_url
        explicit = str(shard_env.get("WW_DATABASE_URL") or shard_env.get("DATABASE_URL") or "").strip()
        if explicit:
            return _normalize_database_url(explicit)
        db_file = str(shard_env.get("CITY_DB_FILE") or "").strip()
        if db_file:
            candidate = shard_dir / "db" / db_file
            if candidate.exists():
                return f"sqlite:///{candidate}"
    env_component_url = _compose_postgres_url(
        {
            "WW_DB_HOST": os.environ.get("WW_DB_HOST", ""),
            "WW_DB_PORT": os.environ.get("WW_DB_PORT", ""),
            "WW_DB_NAME": os.environ.get("WW_DB_NAME", ""),
            "WW_DB_USER": os.environ.get("WW_DB_USER", ""),
            "WW_DB_PASSWORD": os.environ.get("WW_DB_PASSWORD", ""),
        }
    )
    if env_component_url:
        return env_component_url
    explicit = (os.environ.get("WW_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
    if explicit:
        return _normalize_database_url(explicit)
    dw = os.environ.get("WW_DB_PATH", "").strip()
    if dw:
        return f"sqlite:///{dw}"
    for rel in ("db/worldweaver.db", "worldweaver.db"):
        candidate = ROOT / rel
        if candidate.exists():
            return f"sqlite:///{candidate}"
    return None


# ---------------------------------------------------------------------------
# Main repair logic
# ---------------------------------------------------------------------------


def repair_graph(db_url: str, k: int, max_km: float, dry_run: bool) -> dict:
    try:
        from sqlalchemy import create_engine, or_
        from sqlalchemy.orm import sessionmaker
    except ImportError:
        print("ERROR: sqlalchemy not installed.  Run: pip install sqlalchemy")
        sys.exit(1)

    sys.path.insert(0, str(ROOT))
    from src.models import WorldEdge, WorldNode

    kwargs = {"check_same_thread": False} if "sqlite" in db_url else {}
    engine = create_engine(db_url, connect_args=kwargs)
    Session = sessionmaker(bind=engine)

    result = {"orphans_found": 0, "landmarks_stitched": 0, "edges_added": 0, "no_coords": 0}

    with Session() as session:
        # All city-pack location nodes (navigable hubs)
        all_loc_nodes = (
            session.query(WorldNode)
            .filter(WorldNode.node_type == "location")
            .all()
        )
        cp_locations = [
            n for n in all_loc_nodes if (n.metadata_json or {}).get("source") == "city_pack"
        ]

        # All city-pack landmark nodes (real SF places, not yet in path graph)
        all_lm_nodes = (
            session.query(WorldNode)
            .filter(WorldNode.node_type == "landmark")
            .all()
        )
        cp_landmarks = [
            n for n in all_lm_nodes if (n.metadata_json or {}).get("source") == "city_pack"
        ]

        if not cp_locations:
            print("  No city-pack location nodes found.")
            return result

        all_cp_ids = {n.id for n in cp_locations} | {n.id for n in cp_landmarks}

        # All path edges touching any city-pack node
        edges = (
            session.query(WorldEdge)
            .filter(
                WorldEdge.edge_type == "path",
                or_(
                    WorldEdge.source_node_id.in_(all_cp_ids),
                    WorldEdge.target_node_id.in_(all_cp_ids),
                ),
            )
            .all()
        )

        # Build sets of node IDs that already have at least one path edge
        loc_ids = {n.id for n in cp_locations}
        connected_loc_ids: set[int] = set()
        for e in edges:
            if e.source_node_id in loc_ids:
                connected_loc_ids.add(e.source_node_id)
            if e.target_node_id in loc_ids:
                connected_loc_ids.add(e.target_node_id)

        lm_ids = {n.id for n in cp_landmarks}
        connected_lm_ids: set[int] = set()
        for e in edges:
            if e.source_node_id in lm_ids:
                connected_lm_ids.add(e.source_node_id)
            if e.target_node_id in lm_ids:
                connected_lm_ids.add(e.target_node_id)

        # Existing edge pairs to avoid duplicates
        existing_pairs: set[tuple[int, int]] = {(e.source_node_id, e.target_node_id) for e in edges}

        orphan_locs = [n for n in cp_locations if n.id not in connected_loc_ids]
        connected_locs = [n for n in cp_locations if n.id in connected_loc_ids]
        unstitched_lms = [n for n in cp_landmarks if n.id not in connected_lm_ids]

        print(f"  City-pack location nodes : {len(cp_locations)}")
        print(f"    connected              : {len(connected_locs)}")
        print(f"    orphaned               : {len(orphan_locs)}")
        print(f"  City-pack landmark nodes : {len(cp_landmarks)}")
        print(f"    already stitched       : {len(cp_landmarks) - len(unstitched_lms)}")
        print(f"    needs stitching        : {len(unstitched_lms)}")

        result["orphans_found"] = len(orphan_locs)
        result["landmarks_stitched"] = len(unstitched_lms)

        # Candidates for proximity matching: prefer connected locations
        if len(connected_locs) >= 2:
            loc_candidates = connected_locs
        else:
            print(
                "  WARNING: fewer than 2 connected location nodes — treating all"
                " location nodes as candidates."
            )
            loc_candidates = cp_locations

        # Georef index for location candidates
        loc_georef = [
            (n, (n.metadata_json or {}).get("lat"), (n.metadata_json or {}).get("lon"))
            for n in loc_candidates
        ]
        loc_georef_valid = [t for t in loc_georef if t[1] is not None and t[2] is not None]

        new_edges: list[tuple[int, int]] = []

        def _connect(node: "WorldNode", candidates_georef: list, label: str) -> None:
            meta = node.metadata_json or {}
            olat, olon = meta.get("lat"), meta.get("lon")

            if olat is not None and olon is not None and candidates_georef:
                distances = [
                    (n, _haversine_km(olat, olon, lat, lon))
                    for n, lat, lon in candidates_georef
                    if n.id != node.id
                ]
                distances.sort(key=lambda x: x[1])
                chosen = [(n, d) for n, d in distances[:k] if d <= max_km]
                if not chosen and distances:
                    chosen = [distances[0]]  # Always connect to at least one
                for neighbor, dist_km in chosen:
                    for src, tgt in [(node.id, neighbor.id), (neighbor.id, node.id)]:
                        if (src, tgt) not in existing_pairs:
                            new_edges.append((src, tgt))
                            existing_pairs.add((src, tgt))
                    print(f"    {label}: {node.name} ↔ {neighbor.name}  ({dist_km:.2f} km)")
            else:
                result["no_coords"] += 1
                alpha = sorted(
                    [n for n, _, _ in candidates_georef if n.id != node.id],
                    key=lambda n: abs(ord(n.name[0].lower()) - ord(node.name[0].lower()))
                    if n.name and node.name else 999,
                )[:k]
                for neighbor in alpha:
                    for src, tgt in [(node.id, neighbor.id), (neighbor.id, node.id)]:
                        if (src, tgt) not in existing_pairs:
                            new_edges.append((src, tgt))
                            existing_pairs.add((src, tgt))
                    print(f"    {label} (no-coords): {node.name} ↔ {neighbor.name}")

        # ── Pass 1: repair orphan location nodes ─────────────────────────────
        if orphan_locs:
            print(f"\n  [pass 1] Connecting {len(orphan_locs)} orphan location node(s)…")
            for orphan in orphan_locs:
                _connect(orphan, loc_georef_valid, "orphan")

        # ── Pass 2: stitch unconnected landmark nodes to nearest locations ───
        if unstitched_lms:
            print(f"\n  [pass 2] Stitching {len(unstitched_lms)} landmark node(s) to location graph…")
            for lm in unstitched_lms:
                _connect(lm, loc_georef_valid, "landmark")

        print(f"\n  New edges to add: {len(new_edges)}")

        if not dry_run and new_edges:
            for src_id, tgt_id in new_edges:
                session.add(
                    WorldEdge(
                        source_node_id=src_id,
                        target_node_id=tgt_id,
                        edge_type="path",
                        weight=1.0,
                        confidence=0.8,
                        metadata_json={"source": "repair_graph"},
                    )
                )
            session.commit()
            result["edges_added"] = len(new_edges)
            print(f"  Committed {len(new_edges)} new path edges.")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Connect orphan city-pack location nodes to the path graph.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--db-url", default=None, help="SQLAlchemy DB URL")
    parser.add_argument(
        "--shard-dir",
        default=None,
        help="Path to shard directory whose .env should provide DB settings",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=2,
        help="Number of neighbors to connect each orphan to (default: 2)",
    )
    parser.add_argument(
        "--max-km",
        type=float,
        default=5.0,
        help="Max connection distance in km (default: 5.0)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Preview without modifying")
    args = parser.parse_args()

    if args.dry_run:
        print("[dry-run] No changes will be made.\n")

    shard_dir = Path(args.shard_dir).resolve() if args.shard_dir else None
    if shard_dir is not None and not shard_dir.exists():
        print(f"ERROR: shard dir not found: {shard_dir}")
        return 1

    db_url = _resolve_db_url(args.db_url, shard_dir=shard_dir)
    if not db_url:
        print("ERROR: No database found. Set shard WW_DB_* / WW_DATABASE_URL / DATABASE_URL, or ensure sqlite compat DB exists.")
        return 1

    print(f"[repair-graph] db: {db_url}")
    print(f"[repair-graph] k={args.k}, max_km={args.max_km}")

    try:
        counts = repair_graph(db_url, k=args.k, max_km=args.max_km, dry_run=args.dry_run)
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    suffix = "  (dry-run — nothing was changed)" if args.dry_run else ""
    print(f"\nDone.{suffix}")
    if not args.dry_run:
        print(
            f"  {counts['orphans_found']} orphans processed, "
            f"{counts['edges_added']} edges added"
            + (f", {counts['no_coords']} had no coordinates" if counts["no_coords"] else "")
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
