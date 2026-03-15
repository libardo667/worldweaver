"""Maintenance command to refresh embeddings for storylets and world events."""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import SessionLocal, create_tables
from src.services.embedding_service import reembed_storylets
from src.services.world_memory import reembed_world_events

logger = logging.getLogger("reembed")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-embed storylets and world events in bounded batches.",
    )
    parser.add_argument(
        "--scope",
        choices=("storylets", "events", "both"),
        default="both",
        help="Which records to process.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Maximum rows loaded per batch.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report counts without writing embedding updates.",
    )
    return parser.parse_args()


def _log_stats(label: str, stats: Dict[str, int], dry_run: bool) -> None:
    mode = "dry-run" if dry_run else "apply"
    logger.info(
        "%s (%s): scanned=%d updated=%d failed=%d",
        label,
        mode,
        int(stats.get("scanned", 0)),
        int(stats.get("updated", 0)),
        int(stats.get("failed", 0)),
    )


def main() -> int:
    args = _parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    batch_size = max(1, int(args.batch_size))
    create_tables()

    db = SessionLocal()
    try:
        totals = {"scanned": 0, "updated": 0, "failed": 0}

        if args.scope in {"storylets", "both"}:
            storylet_stats = reembed_storylets(
                db=db,
                batch_size=batch_size,
                dry_run=bool(args.dry_run),
            )
            _log_stats("storylets", storylet_stats, bool(args.dry_run))
            for key in totals:
                totals[key] += int(storylet_stats.get(key, 0))

        if args.scope in {"events", "both"}:
            event_stats = reembed_world_events(
                db=db,
                batch_size=batch_size,
                dry_run=bool(args.dry_run),
            )
            _log_stats("events", event_stats, bool(args.dry_run))
            for key in totals:
                totals[key] += int(event_stats.get(key, 0))

        logger.info(
            "completed: scanned=%d updated=%d failed=%d",
            totals["scanned"],
            totals["updated"],
            totals["failed"],
        )
        return 0
    except Exception:
        logger.exception("Re-embedding command failed.")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
