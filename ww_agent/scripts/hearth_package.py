#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Inspect, export, or import one portable resident hearth."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_package import (  # noqa: E402
    HearthPackageError,
    export_hearth_package,
    import_hearth_package,
    inventory_hearth,
)


def _print_error(subject: Path, exc: Exception) -> None:
    print(
        json.dumps(
            {"subject": str(subject), "status": "invalid", "error": str(exc)},
            sort_keys=True,
        )
    )


def main(argv: list[str] | None = None) -> int:
    arguments = list(argv if argv is not None else sys.argv[1:])
    commands = {"inventory", "export", "import"}
    if (
        arguments
        and arguments[0] not in commands
        and arguments[0] not in {"-h", "--help"}
    ):
        arguments.insert(0, "inventory")

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser(
        "inventory", help="inspect without changing or copying the resident"
    )
    inventory_parser.add_argument("home", help="one resident home directory")
    inventory_parser.add_argument(
        "--summary", action="store_true", help="omit the per-file list"
    )

    export_parser = subparsers.add_parser(
        "export", help="write a deterministic portable package"
    )
    export_parser.add_argument("home", help="one stopped resident home directory")
    export_parser.add_argument("package", help="new package path")

    import_parser = subparsers.add_parser(
        "import", help="validate and install a package into a new home"
    )
    import_parser.add_argument("package", help="existing package path")
    import_parser.add_argument("home", help="new resident home directory")

    args = parser.parse_args(arguments)

    home = Path(args.home).expanduser().resolve()
    if args.command == "export":
        package = Path(args.package).expanduser().resolve()
        try:
            report = export_hearth_package(home, package)
        except (HearthPackageError, OSError) as exc:
            _print_error(home, exc)
            return 2
        print(
            json.dumps(
                {
                    "status": "exported",
                    "home": str(home),
                    "package": str(package),
                    "hearth_manifest": report["hearth_manifest"],
                    "file_count": len(report["files"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "import":
        package = Path(args.package).expanduser().resolve()
        try:
            report = import_hearth_package(package, home)
        except (HearthPackageError, OSError) as exc:
            _print_error(package, exc)
            return 2
        print(
            json.dumps(
                {
                    "status": "imported",
                    "home": str(home),
                    "package": str(package),
                    "hearth_manifest": report["hearth_manifest"],
                    "file_count": len(report["files"]),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    try:
        inventory = inventory_hearth(home)
    except (OSError, ValueError) as exc:
        _print_error(home, exc)
        return 2
    report = inventory.to_dict()
    if args.summary:
        report.pop("items", None)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if inventory.blocked else 0


if __name__ == "__main__":
    raise SystemExit(main())
