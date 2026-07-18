#!/usr/bin/env python3
"""Print a content-blind health report over public city chat."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import SessionLocal  # noqa: E402
from src.models import LocationChat  # noqa: E402
from src.services.conversation_health import PublicConversationMessage, analyze_public_conversation  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since-hours", type=float, default=24.0, help="public chat lookback window (0.25-720 hours)")
    parser.add_argument("--minimum-speakers", type=int, default=3, help="minimum population for language metrics (3-100)")
    parser.add_argument("--windows", type=int, default=3, help="ordered comparison windows (2-12)")
    parser.add_argument("--shuffle-seed", type=int, default=0, help="repeatable null-comparison seed")
    args = parser.parse_args(argv)
    if not 0.25 <= args.since_hours <= 720:
        parser.error("--since-hours must be between 0.25 and 720")
    if not 3 <= args.minimum_speakers <= 100:
        parser.error("--minimum-speakers must be between 3 and 100")
    if not 2 <= args.windows <= 12:
        parser.error("--windows must be between 2 and 12")

    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=args.since_hours)
    with SessionLocal() as db:
        rows = db.query(LocationChat).filter(LocationChat.created_at >= since).order_by(LocationChat.created_at.asc()).all()
        messages = [
            PublicConversationMessage(
                speaker_key=str(row.display_name or row.session_id or "").strip(),
                body=str(row.message or ""),
                created_at=row.created_at.replace(tzinfo=timezone.utc) if row.created_at and row.created_at.tzinfo is None else row.created_at,
                location_key=str(row.location or ""),
            )
            for row in rows
            if row.created_at is not None
        ]

    report = analyze_public_conversation(
        messages,
        minimum_speakers=args.minimum_speakers,
        window_count=args.windows,
        shuffle_seed=args.shuffle_seed,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
