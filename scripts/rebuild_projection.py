"""Rebuild world projection state by replaying world events."""

from __future__ import annotations

import argparse
import json
import sys

from src.database import SessionLocal
from src.services.world_memory import rebuild_world_projection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Rebuild event-sourced world projection from WorldEvent history."
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Do not clear existing projection rows before replay.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON output.",
    )
    parser.add_argument(
        "--session-id",
        type=str,
        default=None,
        help="Replay only events for a specific session id.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db = SessionLocal()
    try:
        stats = rebuild_world_projection(
            db=db,
            clear_existing=not args.keep_existing,
            session_id=args.session_id,
        )
    except Exception as exc:
        db.rollback()
        print(f"Projection rebuild failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()
        SessionLocal.remove()

    if args.json:
        print(json.dumps(stats))
    else:
        print(
            "Projection rebuild complete: "
            f"events_processed={stats['events_processed']} "
            f"updates_applied={stats['updates_applied']} "
            f"projection_rows={stats['projection_rows']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
