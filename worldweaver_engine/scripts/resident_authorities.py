#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
"""List or admit resident public identities on one city node."""

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
from src.models import ResidentAuthority, ResidentSessionAuthority  # noqa: E402
from src.services.resident_authority import (  # noqa: E402
    ResidentAuthorityError,
    bind_resident_identity,
)


def _authority_payload(db, row: ResidentAuthority) -> dict[str, object]:
    sessions = db.query(ResidentSessionAuthority).filter(ResidentSessionAuthority.actor_id == row.actor_id).order_by(ResidentSessionAuthority.session_id).all()
    return {
        "actor_id": row.actor_id,
        "hearth_shard_id": row.hearth_shard_id,
        "identity_public_key": row.identity_public_key,
        "identity_key_id": row.identity_key_id,
        "active_runtime_generation": row.active_runtime_generation,
        "recovery_policy_version": row.recovery_policy_version,
        "admission_reason": row.admission_reason,
        "admitted_by": row.admitted_by,
        "bound_at": row.bound_at.isoformat() if row.bound_at else None,
        "sessions": [
            {
                "session_id": session.session_id,
                "runtime_generation": session.runtime_generation,
            }
            for session in sessions
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="list admitted resident public identities")
    admit = commands.add_parser("admit", help="admit one reviewed resident public identity")
    admit.add_argument("--actor-id", required=True)
    admit.add_argument("--hearth-shard-id", required=True)
    admit.add_argument("--identity-public-key", required=True)
    admit.add_argument("--reason", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if settings.shard_type == "world":
        print(
            "ERROR: resident identities are admitted by the city they enter, not by a federation directory.",
            file=sys.stderr,
        )
        return 1

    with SessionLocal() as db:
        try:
            if args.command == "list":
                rows = db.query(ResidentAuthority).order_by(ResidentAuthority.actor_id).all()
                payload: object = [_authority_payload(db, row) for row in rows]
            else:
                row = bind_resident_identity(
                    db,
                    actor_id=args.actor_id,
                    hearth_shard_id=args.hearth_shard_id,
                    identity_public_key=args.identity_public_key,
                    admission_reason=args.reason,
                    admitted_by="local-steward",
                )
                db.commit()
                payload = _authority_payload(db, row)
        except ResidentAuthorityError as exc:
            db.rollback()
            print(
                json.dumps(
                    {"status": "refused", "code": exc.code, "message": str(exc)},
                    sort_keys=True,
                ),
                file=sys.stderr,
            )
            return 1

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
