#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Inspect portable-hearth contents without copying or changing a resident."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_package import inventory_hearth  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", help="one resident home directory")
    parser.add_argument("--summary", action="store_true", help="omit the per-file list")
    args = parser.parse_args(argv)

    home = Path(args.home).expanduser().resolve()
    try:
        inventory = inventory_hearth(home)
    except (OSError, ValueError) as exc:
        print(
            json.dumps(
                {"resident": home.name, "status": "invalid", "error": str(exc)},
                sort_keys=True,
            )
        )
        return 2
    report = inventory.to_dict()
    if args.summary:
        report.pop("items", None)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if inventory.blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
