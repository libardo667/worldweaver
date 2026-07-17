#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Inspect, initialize, or transfer a stopped resident hearth generation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_activation import (  # noqa: E402
    HearthActivationError,
    activate_imported_hearth,
    initialize_hearth_activation,
    inspect_hearth_activation,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", help="source resident home")
    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--initialize",
        action="store_true",
        help="activate generation 1 for a newly manifested stopped home",
    )
    action.add_argument(
        "--transfer-to",
        metavar="IMPORTED_HOME",
        help="retire HOME and activate its already imported copy",
    )
    args = parser.parse_args(argv)
    home = Path(args.home).expanduser().resolve()
    try:
        if args.initialize:
            activation = initialize_hearth_activation(home)
            report = {
                "status": "initialized",
                "home": str(home),
                "activation": activation.to_dict(),
            }
        elif args.transfer_to:
            target = Path(args.transfer_to).expanduser().resolve()
            activation = activate_imported_hearth(home, target)
            report = {
                "status": "transferred",
                "source": str(home),
                "active_home": str(target),
                "activation": activation.to_dict(),
            }
        else:
            report = inspect_hearth_activation(home)
    except (HearthActivationError, OSError) as exc:
        print(
            json.dumps(
                {"status": "invalid", "home": str(home), "error": str(exc)},
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("status") not in {"invalid", "dormant", "retired"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
