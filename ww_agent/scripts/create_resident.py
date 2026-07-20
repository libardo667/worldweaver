#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Create one minimal signed resident home without waking or admitting it."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.resident_creation import (  # noqa: E402
    ResidentCreationError,
    create_dormant_resident,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--residents-dir", type=Path, required=True)
    parser.add_argument("--name", required=True, help="resident's chosen display name")
    parser.add_argument("--host-key", type=Path, required=True)
    parser.add_argument(
        "--entry-location",
        default="",
        help="optional exact city place used on the resident's first attachment",
    )
    args = parser.parse_args(argv)
    try:
        report = create_dormant_resident(
            args.residents_dir,
            display_name=args.name,
            host_transport_private_key_path=args.host_key,
            entry_location=args.entry_location,
        )
    except (ResidentCreationError, OSError, ValueError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
