#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Retire or activate one encrypted, witnessed hearth handoff."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_envelope import (  # noqa: E402
    HearthEnvelopeError,
    load_transport_private_key,
)
from src.identity.hearth_handoff import (  # noqa: E402
    HEARTH_HANDOFF_FILENAME,
    HearthHandoffError,
    load_hearth_handoff_authorization,
)
from src.identity.hearth_receipt import (  # noqa: E402
    HearthReceiptError,
    load_hearth_handoff_receipt,
    write_hearth_handoff_receipt,
)
from src.identity.hearth_remote_activation import (  # noqa: E402
    RemoteHearthActivationError,
    activate_destination_hearth,
    retire_source_hearth,
)
from src.identity.host_witness import (  # noqa: E402
    HostWitnessError,
    load_host_witness_descriptor,
    load_host_witness_private_key,
)
from src.identity.resident_identity import (  # noqa: E402
    ResidentIdentityError,
    load_resident_identity_descriptor,
)


def _private_key_path(variable: str) -> str:
    path = str(os.environ.get(variable) or "").strip()
    if not path:
        raise RemoteHearthActivationError(f"{variable} is required")
    return path


def _new_receipt_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if path.exists() or path.is_symlink():
        raise RemoteHearthActivationError(
            f"refusing to replace existing receipt: {path}"
        )
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise RemoteHearthActivationError(
            f"receipt parent is missing or unsafe: {path.parent}"
        )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    retire = commands.add_parser(
        "retire-source",
        help="retire source generation N and emit its witnessed receipt",
    )
    retire.add_argument("home", help="stopped source resident home")
    retire.add_argument("handoff", help="resident-signed handoff sidecar")
    retire.add_argument("--source-witness", required=True, help="source node.json")
    retire.add_argument("--receipt-output", required=True, help="new receipt path")

    activate = commands.add_parser(
        "activate-destination",
        help="verify source retirement, activate N+1, and emit its receipt",
    )
    activate.add_argument("home", help="dormant destination resident home")
    activate.add_argument("retirement_receipt", help="source retirement receipt")
    activate.add_argument("--source-witness", required=True, help="source node.json")
    activate.add_argument(
        "--destination-witness",
        required=True,
        help="destination node.json",
    )
    activate.add_argument("--receipt-output", required=True, help="new receipt path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    home = Path(args.home).expanduser().resolve()
    subject = Path(args.handoff if args.command == "retire-source" else home)
    try:
        output = _new_receipt_path(args.receipt_output)
        try:
            output.relative_to(home)
        except ValueError:
            pass
        else:
            raise RemoteHearthActivationError(
                "external receipt output must be outside the resident home"
            )
        descriptor = load_resident_identity_descriptor(home)
        transport_private = load_transport_private_key(
            _private_key_path("WW_HEARTH_TRANSPORT_PRIVATE_KEY")
        )
        witness_private = load_host_witness_private_key(
            _private_key_path("WW_HEARTH_WITNESS_PRIVATE_KEY")
        )
        source_witness = load_host_witness_descriptor(args.source_witness)
        if args.command == "retire-source":
            handoff = load_hearth_handoff_authorization(
                args.handoff,
                identity_descriptor=descriptor,
            )
            receipt = retire_source_hearth(
                home,
                handoff,
                source_transport_public_key=transport_private.public_key(),
                source_witness=source_witness,
                source_witness_private_key=witness_private,
            )
            receipt_witness = source_witness
        else:
            handoff = load_hearth_handoff_authorization(
                home / HEARTH_HANDOFF_FILENAME,
                identity_descriptor=descriptor,
            )
            destination_witness = load_host_witness_descriptor(args.destination_witness)
            retirement = load_hearth_handoff_receipt(
                args.retirement_receipt,
                handoff=handoff,
                witness=source_witness,
            )
            receipt = activate_destination_hearth(
                home,
                retirement,
                destination_transport_public_key=transport_private.public_key(),
                source_witness=source_witness,
                destination_witness=destination_witness,
                destination_witness_private_key=witness_private,
            )
            receipt_witness = destination_witness
        write_hearth_handoff_receipt(
            output,
            receipt,
            handoff=handoff,
            witness=receipt_witness,
        )
    except (
        HearthEnvelopeError,
        HearthHandoffError,
        HearthReceiptError,
        HostWitnessError,
        OSError,
        RemoteHearthActivationError,
        ResidentIdentityError,
    ) as exc:
        print(
            json.dumps(
                {"status": "refused", "subject": str(subject), "error": str(exc)},
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(
        json.dumps(
            {
                "status": receipt.phase,
                "home": str(home),
                "receipt": str(output),
                "handoff_receipt": receipt.to_dict(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
