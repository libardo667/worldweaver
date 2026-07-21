#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Create or restore a synthetic resident artifact for cross-process gym tests."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

AGENT_ROOT = Path(__file__).resolve().parents[1]
if str(AGENT_ROOT) not in sys.path:
    sys.path.insert(0, str(AGENT_ROOT))

from src.identity.hearth_manifest import initialize_hearth_manifest  # noqa: E402
from src.identity.hearth_package import export_hearth_package  # noqa: E402
from src.identity.loader import LoopTuning, ResidentIdentity  # noqa: E402
from src.runtime.ledger import (  # noqa: E402
    append_runtime_event,
    load_resident_process_envelope,
)
from src.runtime.private_artifact import (  # noqa: E402
    PrivateArtifactError,
    describe_private_artifact,
    restore_private_artifact,
)
from src.runtime.process_state import ResidentProcessBinding  # noqa: E402
from src.runtime.reference_core import (  # noqa: E402
    ReferenceResidentCore,
    build_reference_scheduled_return,
)
from src.world.client import SceneData, scene_data_from_payload  # noqa: E402

_SYNTHETIC_PRIVATE_ACTIVITY = (
    "Privately compare the synthetic blue and green route notes."
)
_SYNTHETIC_ACTIVITY_ID = "activity-synthetic-route-notes"


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
            "activity_id": _SYNTHETIC_ACTIVITY_ID,
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
    return_at = _parse_time(args.return_at)
    scheduled_return = build_reference_scheduled_return(
        actor_id=args.actor_id,
        activity_id=_SYNTHETIC_ACTIVITY_ID,
        due_at=return_at,
    )
    return {
        "schema": "worldweaver.synthetic-gym-private-artifact",
        "schema_version": 2,
        "descriptor": descriptor.as_dict(),
        "process": binding.as_dict(),
        "scheduled_return": scheduled_return.as_payload(),
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


def _parse_time(raw: str) -> datetime:
    parsed = datetime.fromisoformat(str(raw or "").strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class _FixtureWorld:
    def __init__(self, scene: SceneData):
        self.scene = scene

    async def get_scene(self, _session_id: str) -> SceneData:
        return self.scene

    async def get_location_chat(self, _location: str, *, session_id: str) -> tuple:
        del session_id
        return ()

    async def get_pending_correspondence(
        self, _session_id: str, *, limit: int = 10
    ) -> tuple:
        del limit
        return ()

    async def acknowledge_correspondence(
        self, _session_id: str, _message_ids: tuple[int, ...]
    ) -> dict:
        return {"acknowledged_ids": []}


class _ScriptedWaitModel:
    def __init__(self) -> None:
        self.call_count = 0

    async def complete_json(self, *_args, **_kwargs) -> dict:
        self.call_count += 1
        return {"choice": "wait"}


async def _refuse_effect(*_args, **_kwargs) -> dict:
    raise RuntimeError("the scripted wait fixture may not perform an action or read")


def _handle_return(args: argparse.Namespace) -> dict:
    home = args.home.resolve()
    expected_process = ResidentProcessBinding.from_dict(
        _read_object(args.expected_process.resolve())
    )
    restored_process = load_resident_process_envelope(home / "memory")
    if restored_process is None:
        raise PrivateArtifactError("restored resident has no process checkpoint")
    if ResidentProcessBinding.from_dict(restored_process) != expected_process:
        raise PrivateArtifactError("restored resident process binding does not match")

    scene_payload = _read_object(args.scene.resolve())
    scene = scene_data_from_payload(
        scene_payload,
        session_id=expected_process.session_id,
    )
    model = _ScriptedWaitModel()
    identity = ResidentIdentity(
        name="synthetic_gym_resident",
        actor_id=expected_process.actor_id,
        soul="You are a synthetic gym participant.",
        canonical_soul="You are a synthetic gym participant.",
        growth_soul="",
        vibe="",
        core="",
        voice_seed=[],
        tuning=LoopTuning(),
    )
    core = ReferenceResidentCore(
        identity=identity,
        memory_dir=home / "memory",
        world=_FixtureWorld(scene),
        llm=model,
        session_id=expected_process.session_id,
        effector=_refuse_effect,
        information_access=_refuse_effect,
        tick_seconds=2,
        model=expected_process.model_id,
    )
    result = asyncio.run(
        core.handle_scheduled_return(
            args.event_id,
            now=_parse_time(args.now),
        )
    )
    return {
        "schema": "worldweaver.synthetic-gym-return-result",
        "schema_version": 1,
        "status": str(result.get("status") or ""),
        "event_id": str(result.get("event_id") or ""),
        "activation_status": str(result.get("activation_status") or ""),
        "choice": str(result.get("choice") or "none"),
        "model_call_count": model.call_count,
    }


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
    handle_return = subparsers.add_parser(
        "handle-return",
        help="offer a due return to the restored reference core with a scripted wait",
    )
    handle_return.add_argument("--home", type=Path, required=True)
    handle_return.add_argument("--expected-process", type=Path, required=True)
    handle_return.add_argument("--scene", type=Path, required=True)
    handle_return.add_argument("--event-id", required=True)
    handle_return.add_argument("--now", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        handlers = {
            "create-fixture": _create_fixture,
            "restore": _restore,
            "handle-return": _handle_return,
        }
        result = handlers[args.command](args)
    except (OSError, PrivateArtifactError, ValueError) as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
