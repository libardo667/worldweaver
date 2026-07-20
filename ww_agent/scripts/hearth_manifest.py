#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Inspect or explicitly initialize one resident's portable hearth manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_manifest import (  # noqa: E402
    HearthManifestError,
    initialize_hearth_manifest,
    inspect_hearth_manifest,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("home", help="one resident home directory")
    parser.add_argument(
        "--initialize",
        action="store_true",
        help="write the initial manifest; default inspection never writes",
    )
    args = parser.parse_args(argv)

    home = Path(args.home).expanduser().resolve()
    if not home.is_dir() or not (home / "identity").is_dir():
        print(
            json.dumps(
                {
                    "resident": home.name,
                    "status": "invalid",
                    "error": "resident home is missing identity/",
                },
                sort_keys=True,
            )
        )
        return 2

    if args.initialize:
        try:
            initialize_hearth_manifest(home)
        except (HearthManifestError, OSError) as exc:
            print(
                json.dumps(
                    {"resident": home.name, "status": "invalid", "error": str(exc)},
                    sort_keys=True,
                )
            )
            return 1

    report = inspect_hearth_manifest(home)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
