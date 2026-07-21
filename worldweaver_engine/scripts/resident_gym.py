#!/usr/bin/env python3
# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

"""Run a deterministic resident-gym episode without a live shard or model."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ENGINE_ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_ROOT = ENGINE_ROOT.parent
if str(ENGINE_ROOT) not in sys.path:
    sys.path.insert(0, str(ENGINE_ROOT))

from src.api.game import _state_managers  # noqa: E402
from src.database import Base  # noqa: E402
from src.services.gym_presentation import (  # noqa: E402
    render_html,
    render_terminal,
    render_terminal_record,
    render_terminal_stream_footer,
    render_terminal_stream_header,
)
from src.services.resident_gym import (  # noqa: E402
    ProductionRuleGym,
    finish_quiet_interval,
    prepare_quiet_interval,
    run_first_conversation,
    run_quiet_interval,
    run_waiting_letter,
)
from src.services.session_service import _session_locks  # noqa: E402


def _agent_artifact_command(*arguments: str) -> dict:
    completed = subprocess.run(
        [sys.executable, "scripts/resident_gym_artifact.py", *arguments],
        cwd=WORKSPACE_ROOT / "ww_agent",
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "resident process failed")
    payload = json.loads(completed.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("resident process returned an invalid result")
    return payload


def _memory_database():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def _run_scripted_resident_return(db, *, record_observer=None):
    """Show the stop, due return, lost acknowledgement, and safe retry path."""

    with tempfile.TemporaryDirectory(prefix="worldweaver-gym-return-") as raw_temp:
        temp = Path(raw_temp)
        artifact = _agent_artifact_command(
            "create-fixture",
            "--home",
            str(temp / "source-resident"),
            "--package",
            str(temp / "resident.wwhearth"),
            "--actor-id",
            "gym-afternoon-actor-mara",
            "--world-id",
            "gym-long-afternoon-world",
            "--session-id",
            "gym-afternoon-mara",
            "--started-at",
            "2026-07-20T12:00:00+00:00",
            "--return-at",
            "2026-07-22T12:00:00+00:00",
        )
        process = artifact["process"]
        scheduled_return = artifact["scheduled_return"]
        descriptor_path = temp / "descriptor.json"
        process_path = temp / "process.json"
        scene_path = temp / "scene.json"
        descriptor_path.write_text(json.dumps(artifact["descriptor"]), encoding="utf-8")
        process_path.write_text(json.dumps(process), encoding="utf-8")

        gym = prepare_quiet_interval(
            db,
            record_observer=record_observer,
            mara_implementation="reference_resident_scripted_wait",
        )
        gym.bind_participant_artifacts(
            "gym-afternoon-mara",
            adapter_id=process["adapter"]["id"],
            adapter_version=process["adapter"]["version"],
            model_id=process["model"]["id"],
            private_state=artifact["descriptor"],
        )
        gym.schedule_resident_return(
            "gym-afternoon-mara",
            resident_event_id=scheduled_return["event_id"],
            activity_id=scheduled_return["activity_id"],
            due_at=datetime.fromisoformat(scheduled_return["due_at"]),
        )
        first_checkpoint = json.loads(json.dumps(gym.checkpoint()))
        _agent_artifact_command(
            "restore",
            "--package",
            str(temp / "resident.wwhearth"),
            "--home",
            str(temp / "restored-resident"),
            "--descriptor",
            str(descriptor_path),
            "--expected-process",
            str(process_path),
        )

        first_engine, first_db = _memory_database()
        replay_engine, replay_db = _memory_database()
        try:
            first = ProductionRuleGym.from_checkpoint(
                first_db,
                first_checkpoint,
                record_observer=record_observer,
            )
            inspection = first.offer_next_scheduled()[0]
            first.inspect_sublocation(
                parent_location=str(inspection.payload["parent_location"]),
                sublocation_id=str(inspection.payload["sublocation_id"]),
            )
            first.acknowledge_scheduled((inspection.event_id,))
            due = first.offer_next_scheduled()[0]

            def handle_return(event, scene):
                scene_path.write_text(json.dumps(scene), encoding="utf-8")
                return _agent_artifact_command(
                    "handle-return",
                    "--home",
                    str(temp / "restored-resident"),
                    "--expected-process",
                    str(process_path),
                    "--scene",
                    str(scene_path),
                    "--event-id",
                    str(event.payload["resident_event_id"]),
                    "--now",
                    event.due_at.isoformat(),
                )

            first.deliver_resident_return(due, handle_return)
            lost_ack_checkpoint = json.loads(json.dumps(first.checkpoint()))

            replay = ProductionRuleGym.from_checkpoint(
                replay_db,
                lost_ack_checkpoint,
                record_observer=record_observer,
            )
            retried = replay.offer_next_scheduled()[0]
            replay.deliver_resident_return(retried, handle_return)
            replay.acknowledge_scheduled((retried.event_id,))
            return finish_quiet_interval(replay)
        finally:
            first_db.close()
            replay_db.close()
            first_engine.dispose()
            replay_engine.dispose()
            _state_managers.clear()
            _session_locks.clear()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run a deterministic production-rule resident gym episode."
    )
    parser.add_argument(
        "--episode",
        choices=("footbridge", "waiting-letter", "quiet-interval", "resident-return"),
        default="footbridge",
        help="episode to run (default: footbridge)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="self-contained HTML result (default: .runs/gym/<episode>.html)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the structural episode JSON instead of the terminal view",
    )
    parser.add_argument(
        "--no-stream",
        action="store_true",
        help="print the old complete terminal report after the episode finishes",
    )
    args = parser.parse_args()

    _state_managers.clear()
    _session_locks.clear()
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    stream = not args.json and not args.no_stream
    episode_titles = {
        "footbridge": "The Footbridge Hello",
        "waiting-letter": "The Waiting Letter",
        "quiet-interval": "The Long Afternoon",
        "resident-return": "The Kept Appointment",
    }
    if stream:
        print(render_terminal_stream_header(episode_titles[args.episode]), flush=True)

    def show_record(record):
        print(render_terminal_record(record), flush=True)

    try:
        with session_factory() as db:
            runners = {
                "footbridge": run_first_conversation,
                "waiting-letter": run_waiting_letter,
                "quiet-interval": run_quiet_interval,
                "resident-return": _run_scripted_resident_return,
            }
            result = runners[args.episode](
                db,
                record_observer=show_record if stream else None,
            )
        default_names = {
            "footbridge": "footbridge-hello.html",
            "waiting-letter": "waiting-letter.html",
            "quiet-interval": "long-afternoon.html",
            "resident-return": "kept-appointment.html",
        }
        default_name = default_names[args.episode]
        output = (
            (args.output or WORKSPACE_ROOT / ".runs" / "gym" / default_name)
            .expanduser()
            .resolve()
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(render_html(result), encoding="utf-8")
        if args.json:
            print(json.dumps(result.as_payload(), indent=2, ensure_ascii=False))
        elif stream:
            print(render_terminal_stream_footer(result), flush=True)
        else:
            print(render_terminal(result))
        print(f"Visual episode: {output}")
    finally:
        engine.dispose()
        _state_managers.clear()
        _session_locks.clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
