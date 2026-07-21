#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Create or restore a synthetic resident artifact for cross-process gym tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_manifest import initialize_hearth_manifest  # noqa: E402
from src.identity.hearth_package import export_hearth_package  # noqa: E402
from src.runtime.ledger import append_runtime_event  # noqa: E402
from src.runtime.private_artifact import (  # noqa: E402
    PrivateArtifactError,
    describe_private_artifact,
    restore_private_artifact,
)
from src.runtime.process_state import ResidentProcessBinding  # noqa: E402

_SYNTHETIC_PRIVATE_ACTIVITY = (
    "Privately compare the synthetic blue and green route notes."
)


def _read_object(path: Path) -> dict:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PrivateArtifactError(f"could not read JSON input: {path}") from exc
    if not isinstance(raw, dict):
        raise PrivateArtifactError(f"JSON input must be an object: {path}")
    return raw


def _create_fixture(args: argparse.Namespace) -> dict:
    home = args.home.resolve()
    package = args.package.resolve()
    if home.exists() or home.is_symlink():
        raise PrivateArtifactError("synthetic resident home already exists")
    if package.exists() or package.is_symlink():
        raise PrivateArtifactError("synthetic resident package already exists")
    home.joinpath("identity").mkdir(parents=True)
    home.joinpath("identity", "resident_id.txt").write_text(
        f"{args.actor_id}\n", encoding="utf-8"
    )
    manifest = initialize_hearth_manifest(home)
    binding = ResidentProcessBinding(
        actor_id=args.actor_id,
        hearth_shard_id=manifest.hearth_shard_id,
        runtime_generation=manifest.runtime_generation,
        attachment_kind="city",
        world_id=args.world_id,
        city_id=args.city_id,
        session_id=args.session_id,
        model_id=args.model_id,
    )
    memory_dir = home / "memory"
    append_runtime_event(
        memory_dir,
        event_type="reference_process_bound",
        payload=binding.as_dict(),
        ts=args.started_at,
    )
    append_runtime_event(
        memory_dir,
        event_type="reference_activity_continued",
        payload={
            "activity_state_version": 1,
            "activity_id": "activity-synthetic-route-notes",
            "activity": _SYNTHETIC_PRIVATE_ACTIVITY,
            "opened_at": args.started_at,
            "return_at": args.return_at,
            "wake_on": ["local_speech"],
        },
        ts=args.started_at,
    )
    package.parent.mkdir(parents=True, exist_ok=True)
    export_hearth_package(home, package)
    descriptor = describe_private_artifact(package)
    return {
        "schema": "worldweaver.synthetic-gym-private-artifact",
        "schema_version": 1,
        "descriptor": descriptor.as_dict(),
        "process": binding.as_dict(),
    }


def _restore(args: argparse.Namespace) -> dict:
    descriptor = _read_object(args.descriptor.resolve())
    process = ResidentProcessBinding.from_dict(
        _read_object(args.expected_process.resolve())
    )
    return restore_private_artifact(
        args.package.resolve(),
        args.home.resolve(),
        descriptor=descriptor,
        expected_process=process,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    fixture = subparsers.add_parser(
        "create-fixture",
        help="create a new synthetic home and stopped portable artifact",
    )
    fixture.add_argument("--home", type=Path, required=True)
    fixture.add_argument("--package", type=Path, required=True)
    fixture.add_argument("--actor-id", required=True)
    fixture.add_argument("--world-id", required=True)
    fixture.add_argument("--city-id", default="")
    fixture.add_argument("--session-id", required=True)
    fixture.add_argument("--model-id", default="test/reference-policy-v1")
    fixture.add_argument("--started-at", required=True)
    fixture.add_argument("--return-at", required=True)

    restore = subparsers.add_parser(
        "restore",
        help="verify and restore into a new synthetic resident home",
    )
    restore.add_argument("--package", type=Path, required=True)
    restore.add_argument("--home", type=Path, required=True)
    restore.add_argument("--descriptor", type=Path, required=True)
    restore.add_argument("--expected-process", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = (
            _create_fixture(args)
            if args.command == "create-fixture"
            else _restore(args)
        )
    except (OSError, PrivateArtifactError, ValueError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
