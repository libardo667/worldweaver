#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Manage the federation directory's explicit node trust decisions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ENGINE_ROOT = Path(__file__).resolve().parent.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.config import settings  # noqa: E402
from src.database import SessionLocal  # noqa: E402
from src.models import FederationNodeTrustEvent, FederationShard  # noqa: E402
from src.services.federation_node_trust import (  # noqa: E402
    FederationNodeTrustError,
    admit_node,
    recover_node_key,
    revoke_node,
)


def _node_payload(node: FederationShard) -> dict[str, object]:
    return {
        "node_id": node.shard_id,
        "shard_type": node.shard_type,
        "city_id": node.city_id,
        "public_key": node.public_key,
        "admission_state": node.admission_state,
        "admitted_at": node.admitted_at.isoformat() if node.admitted_at else None,
        "revoked_at": node.revoked_at.isoformat() if node.revoked_at else None,
        "revocation_reason": node.revocation_reason,
        "key_recovered_at": node.key_recovered_at.isoformat() if node.key_recovered_at else None,
        "registered_url": node.shard_url or None,
        "last_pulse_at": node.last_pulse_ts.isoformat() if node.last_pulse_ts else None,
    }


def _trust_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--node-id", required=True)
    parser.add_argument("--public-key", required=True)
    parser.add_argument("--shard-type", required=True, choices=("city", "world", "neighborhood"))
    parser.add_argument("--city-id", default="")
    parser.add_argument("--reason", required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage nodes admitted to this federation directory.")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="list admitted and revoked nodes")
    history = commands.add_parser("history", help="show the append-only trust history for one node")
    history.add_argument("node_id")

    admit = commands.add_parser("admit", help="admit a new public node descriptor")
    _trust_arguments(admit)

    revoke = commands.add_parser("revoke", help="revoke a known node identity")
    revoke.add_argument("node_id")
    revoke.add_argument("--reason", required=True)

    recover = commands.add_parser("recover", help="replace the key of a previously revoked node")
    _trust_arguments(recover)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if settings.shard_type != "world":
        print("ERROR: node trust can only be managed on a federation directory.", file=sys.stderr)
        return 1

    with SessionLocal() as db:
        try:
            if args.command == "list":
                nodes = db.query(FederationShard).order_by(FederationShard.shard_id).all()
                payload: object = [_node_payload(node) for node in nodes]
            elif args.command == "history":
                events = db.query(FederationNodeTrustEvent).filter(FederationNodeTrustEvent.node_id == args.node_id).order_by(FederationNodeTrustEvent.id).all()
                payload = [
                    {
                        "event_id": event.id,
                        "node_id": event.node_id,
                        "event_type": event.event_type,
                        "previous_public_key": event.previous_public_key,
                        "public_key": event.public_key,
                        "reason": event.reason,
                        "created_at": event.created_at.isoformat() if event.created_at else None,
                    }
                    for event in events
                ]
            elif args.command == "admit":
                node = admit_node(
                    db,
                    node_id=args.node_id,
                    public_key=args.public_key,
                    shard_type=args.shard_type,
                    city_id=args.city_id,
                    reason=args.reason,
                )
                payload = _node_payload(node)
            elif args.command == "revoke":
                payload = _node_payload(revoke_node(db, node_id=args.node_id, reason=args.reason))
            else:
                node = recover_node_key(
                    db,
                    node_id=args.node_id,
                    public_key=args.public_key,
                    shard_type=args.shard_type,
                    city_id=args.city_id,
                    reason=args.reason,
                )
                payload = _node_payload(node)
        except FederationNodeTrustError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
