#!/usr/bin/env python3
"""Deterministic WorldProjection rebuild maintenance script."""

import argparse
import logging
import sys

# Ensure src is in python path if run directly
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.database import SessionLocal
from src.services.world_memory import rebuild_world_projection

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main() -> None:
    parser = argparse.ArgumentParser(description="Deterministic WorldProjection rebuild tool.")
    parser.add_argument(
        "--session-id", 
        help="Only rebuild projection for a specific session_id", 
        default=None
    )
    parser.add_argument(
        "--keep-existing", 
        action="store_true", 
        help="Do not clear existing projection rows before rebuilding"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        logging.info(f"Starting projection rebuild (session_id={args.session_id}, clear_existing={not args.keep_existing})")
        metrics = rebuild_world_projection(
            db,
            clear_existing=not args.keep_existing,
            session_id=args.session_id,
        )
        logging.info(
            "Rebuild complete: processed %r events, applied %r updates. Total rows now %r.",
            metrics.get("events_processed"),
            metrics.get("updates_applied"),
            metrics.get("projection_rows"),
        )
    except Exception as e:
        logging.error("Rebuild failed: %s", e)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
