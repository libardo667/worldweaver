#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Initialize or inspect one host's private hearth transport identity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.services.hearth_transport import (  # noqa: E402
    HearthTransportDescriptor,
    HearthTransportError,
    create_hearth_transport_private_key,
    descriptor_for_hearth_transport_private_key,
    write_hearth_transport_descriptor,
)


def _load_descriptor(path: Path) -> HearthTransportDescriptor:
    if not path.is_file() or path.is_symlink():
        raise HearthTransportError(
            f"Hearth transport descriptor is missing or unsafe: {path}"
        )
    try:
        return HearthTransportDescriptor.from_dict(
            json.loads(path.read_text(encoding="utf-8"))
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HearthTransportError(
            f"Could not load hearth transport descriptor: {path}"
        ) from exc


def ensure_identity(
    private_key_path: Path,
    descriptor_path: Path | None,
) -> tuple[str, HearthTransportDescriptor]:
    """Create missing identity material or verify an existing complete pair."""

    private_exists = private_key_path.exists() or private_key_path.is_symlink()
    descriptor_exists = bool(
        descriptor_path is not None
        and (descriptor_path.exists() or descriptor_path.is_symlink())
    )
    if descriptor_exists and not private_exists:
        raise HearthTransportError(
            "Refusing to replace a public descriptor whose private key is missing."
        )

    if private_exists:
        derived = descriptor_for_hearth_transport_private_key(private_key_path)
        status = "existing"
    else:
        derived = create_hearth_transport_private_key(private_key_path)
        status = "created"

    if descriptor_path is not None:
        if descriptor_exists:
            recorded = _load_descriptor(descriptor_path)
            if recorded != derived:
                raise HearthTransportError(
                    "Public hearth transport descriptor does not match its private key."
                )
        else:
            write_hearth_transport_descriptor(descriptor_path, derived)
            status = "created" if not private_exists else "repaired"
    return status, derived


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-key", required=True)
    parser.add_argument(
        "--descriptor",
        help="optional public descriptor path; omit to print it without writing",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    private_path = Path(args.private_key).expanduser()
    descriptor_path = Path(args.descriptor).expanduser() if args.descriptor else None
    try:
        status, descriptor = ensure_identity(private_path, descriptor_path)
    except HearthTransportError as exc:
        print(
            json.dumps(
                {"status": "refused", "message": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1
    print(
        json.dumps(
            {"status": status, "descriptor": descriptor.to_dict()},
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
