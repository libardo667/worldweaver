#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Found one ordinary-space policy through the trusted steward setup seam."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import SessionLocal  # noqa: E402
from src.services.space_access import SpaceAccessError, found_space_policy  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--location", required=True)
    parser.add_argument("--controller-actor-id", required=True)
    parser.add_argument(
        "--mode",
        choices=("public", "requestable", "private", "closed"),
        default="private",
    )
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        row = found_space_policy(
            db,
            location=args.location,
            controller_actor_id=args.controller_actor_id,
            mode=args.mode,
            note=args.note,
        )
    except SpaceAccessError as exc:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "code": exc.code,
                    "message": str(exc),
                },
                sort_keys=True,
            )
        )
        return 1
    finally:
        db.close()

    print(
        json.dumps(
            {
                "status": "ready",
                "location": row.location,
                "mode": row.mode,
                "controller_actor_id": row.controller_actor_id,
                "revision": row.revision,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
