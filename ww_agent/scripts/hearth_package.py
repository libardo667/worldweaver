#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Inspect, export, or import one portable resident hearth."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_package import (  # noqa: E402
    HearthPackageError,
    export_hearth_package,
    import_encrypted_hearth_package,
    import_hearth_package,
    inventory_hearth,
)
from src.identity.hearth_envelope import (  # noqa: E402
    HearthEnvelopeError,
    load_transport_private_key,
)
from src.identity.resident_identity import (  # noqa: E402
    ResidentIdentityError,
    load_resident_identity_descriptor_file,
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
    commands = {"inventory", "export", "import", "import-encrypted"}
    if arguments and arguments[0] not in commands and arguments[0] not in {"-h", "--help"}:
        arguments.insert(0, "inventory")

    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory", help="inspect without changing or copying the resident")
    inventory_parser.add_argument("home", help="one resident home directory")
    inventory_parser.add_argument("--summary", action="store_true", help="omit the per-file list")

    export_parser = subparsers.add_parser("export", help="write a deterministic portable package")
    export_parser.add_argument("home", help="one stopped resident home directory")
    export_parser.add_argument("package", help="new package path")

    import_parser = subparsers.add_parser("import", help="validate and install a package into a new home")
    import_parser.add_argument("package", help="existing package path")
    import_parser.add_argument("home", help="new resident home directory")

    encrypted_import_parser = subparsers.add_parser(
        "import-encrypted",
        help="verify and install a resident-signed package addressed to this host",
    )
    encrypted_import_parser.add_argument("package", help="existing encrypted package path")
    encrypted_import_parser.add_argument("home", help="new resident home directory")
    encrypted_import_parser.add_argument(
        "--resident-identity",
        required=True,
        help="reviewed safe-to-share resident identity card",
    )

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
    if args.command in {"import", "import-encrypted"}:
        package = Path(args.package).expanduser().resolve()
        try:
            if args.command == "import-encrypted":
                key_path = str(os.environ.get("WW_HEARTH_TRANSPORT_PRIVATE_KEY") or "").strip()
                if not key_path:
                    raise HearthPackageError("WW_HEARTH_TRANSPORT_PRIVATE_KEY is required for encrypted import")
                identity = load_resident_identity_descriptor_file(Path(args.resident_identity).expanduser().resolve())
                report = import_encrypted_hearth_package(
                    package,
                    home,
                    recipient_transport_private_key=load_transport_private_key(key_path),
                    expected_resident_identity_public_key=identity.identity_public_key,
                    expected_actor_id=identity.actor_id,
                    expected_hearth_shard_id=identity.hearth_shard_id,
                )
            else:
                report = import_hearth_package(package, home)
        except (
            HearthEnvelopeError,
            HearthPackageError,
            ResidentIdentityError,
            OSError,
        ) as exc:
            _print_error(package, exc)
            return 2
        print(
            json.dumps(
                {
                    "status": "imported-encrypted" if args.command == "import-encrypted" else "imported",
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
