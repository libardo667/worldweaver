# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

import json
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from src.database import Base
from src.models import SessionVars
from src.services.gym_checkpoint import GymCheckpointError, seal_checkpoint
from src.services.resident_gym import (
    ProductionRuleGym,
    finish_quiet_interval,
    prepare_quiet_interval,
)
from src.services.session_service import clear_session_caches


def _memory_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine)()


def _close(engine, session) -> None:
    session.close()
    engine.dispose()
    clear_session_caches()


def _agent_artifact_command(*arguments: str) -> dict:
    workspace = Path(__file__).resolve().parents[3]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym_artifact.py",
            *arguments,
        ],
        cwd=workspace / "ww_agent",
        text=True,
        capture_output=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


def test_quiet_interval_resumes_to_the_same_result_after_a_real_stop():
    uninterrupted_engine, uninterrupted_db = _memory_session()
    source_engine, source_db = _memory_session()
    target_engine, target_db = _memory_session()
    try:
        clear_session_caches()
        uninterrupted = finish_quiet_interval(
            prepare_quiet_interval(uninterrupted_db)
        ).as_payload()

        clear_session_caches()
        stopped = prepare_quiet_interval(source_db)
        checkpoint = json.loads(json.dumps(stopped.checkpoint()))
        assert len(checkpoint["scheduler"]["pending"]) == 2
        assert checkpoint["captured_at"] == "2026-07-20T12:00:00+00:00"

        resumed_records = []
        resumed = ProductionRuleGym.from_checkpoint(
            target_db,
            checkpoint,
            record_observer=resumed_records.append,
        )
        assert (
            resumed.scheduled_checkpoint()["pending"]
            == checkpoint["scheduler"]["pending"]
        )
        restarted = finish_quiet_interval(resumed).as_payload()

        assert restarted == uninterrupted
        checkpoint_record_count = len(checkpoint["gym"]["records"])
        assert [record.sequence for record in resumed_records] == list(
            range(checkpoint_record_count + 1, len(restarted["records"]) + 1)
        )
    finally:
        _close(uninterrupted_engine, uninterrupted_db)
        _close(source_engine, source_db)
        _close(target_engine, target_db)


def test_checkpoint_rejects_damage_and_identity_substitution_before_restore():
    source_engine, source_db = _memory_session()
    target_engine, target_db = _memory_session()
    try:
        clear_session_caches()
        checkpoint = prepare_quiet_interval(source_db).checkpoint()

        damaged = json.loads(json.dumps(checkpoint))
        damaged["scenario"]["scenario_seed"] = 99
        with pytest.raises(GymCheckpointError, match="integrity"):
            ProductionRuleGym.from_checkpoint(target_db, damaged)

        body = json.loads(json.dumps(checkpoint))
        body.pop("checkpoint_id")
        body.pop("integrity")
        gym_mara = next(
            participant
            for participant in body["gym"]["participants"]
            if participant["session_id"] == "gym-afternoon-mara"
        )
        checkpoint_mara = next(
            participant
            for participant in body["participants"]
            if participant["session_id"] == "gym-afternoon-mara"
        )
        gym_mara["actor_id"] = "substituted-actor"
        checkpoint_mara["actor_id"] = "substituted-actor"
        substituted = seal_checkpoint(body)
        with pytest.raises(GymCheckpointError, match="does not match participant"):
            ProductionRuleGym.from_checkpoint(target_db, substituted)

        assert target_db.query(SessionVars).count() == 0
    finally:
        _close(source_engine, source_db)
        _close(target_engine, target_db)


def test_checkpoint_refuses_to_replace_an_in_use_database():
    source_engine, source_db = _memory_session()
    target_engine, target_db = _memory_session()
    try:
        clear_session_caches()
        checkpoint = prepare_quiet_interval(source_db).checkpoint()
        target_db.add(
            SessionVars(session_id="already-here", vars={"location": "Elsewhere"})
        )
        target_db.commit()

        with pytest.raises(GymCheckpointError, match="no application data"):
            ProductionRuleGym.from_checkpoint(target_db, checkpoint)

        assert target_db.query(SessionVars).one().session_id == "already-here"
    finally:
        _close(source_engine, source_db)
        _close(target_engine, target_db)


def test_participant_private_artifacts_are_bound_by_metadata_not_embedded():
    source_engine, source_db = _memory_session()
    try:
        clear_session_caches()
        gym = prepare_quiet_interval(source_db)
        gym.bind_participant_artifacts(
            "gym-afternoon-mara",
            adapter_id="worldweaver.reference-resident",
            adapter_version=2,
            model_id="reference-policy-v1",
            private_state={
                "custody": "participant_private",
                "format": "worldweaver.hearth-package",
                "format_version": 1,
                "artifact_id": "resident-checkpoint-17",
                "sha256": "a" * 64,
                "byte_length": 4096,
            },
        )
        checkpoint = gym.checkpoint()
        mara = next(
            participant
            for participant in checkpoint["participants"]
            if participant["session_id"] == "gym-afternoon-mara"
        )

        assert mara["private_state"] == {
            "custody": "participant_private",
            "format": "worldweaver.hearth-package",
            "format_version": 1,
            "artifact_id": "resident-checkpoint-17",
            "sha256": "a" * 64,
            "byte_length": 4096,
        }
        assert "private prose that must stay outside the envelope" not in json.dumps(
            checkpoint
        )

        with pytest.raises(GymCheckpointError, match="binding"):
            gym.bind_participant_artifacts(
                "gym-afternoon-mara",
                adapter_id="",
                adapter_version=2,
                model_id="reference-policy-v1",
            )
    finally:
        _close(source_engine, source_db)


def test_resident_return_response_must_match_before_queue_acknowledgement():
    engine, db = _memory_session()
    try:
        gym = prepare_quiet_interval(db)
        gym.bind_participant_artifacts(
            "gym-afternoon-mara",
            adapter_id="worldweaver.reference-resident",
            adapter_version=2,
            model_id="reference-policy-v1",
            private_state={
                "custody": "participant_private",
                "format": "worldweaver.hearth-package",
                "format_version": 1,
                "artifact_id": "resident-checkpoint-17",
                "sha256": "a" * 64,
                "byte_length": 4096,
            },
        )
        queued = gym.schedule_resident_return(
            "gym-afternoon-mara",
            resident_event_id="resident-return-expected",
            activity_id="activity-expected",
            due_at=gym.clock.now() + timedelta(hours=1),
        )
        offered = gym.offer_next_scheduled()
        assert [event.event_id for event in offered] == [queued.event_id]

        with pytest.raises(ValueError, match="does not match"):
            gym.deliver_resident_return(
                offered[0],
                lambda _event, _scene: {
                    "status": "processed",
                    "event_id": "resident-return-other",
                    "choice": "wait",
                    "model_call_count": 1,
                },
            )

        assert [item["event_id"] for item in gym.scheduled_checkpoint()["pending"]] == [
            queued.event_id,
            "scheduled-00000001",
            "scheduled-00000002",
        ]
        record = gym.result().records[-1]
        assert record.kind == "resident_activation_interrupted"
        assert record.detail["reason"] == "return_binding_mismatch"
    finally:
        _close(engine, db)


def test_engine_and_private_resident_artifact_restart_across_processes(tmp_path):
    uninterrupted_engine, uninterrupted_db = _memory_session()
    source_engine, source_db = _memory_session()
    target_engine, target_db = _memory_session()
    try:
        artifact = _agent_artifact_command(
            "create-fixture",
            "--home",
            str(tmp_path / "source-resident"),
            "--package",
            str(tmp_path / "resident.wwhearth"),
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
        assert "synthetic blue" not in json.dumps(artifact)

        clear_session_caches()
        uninterrupted = finish_quiet_interval(
            prepare_quiet_interval(uninterrupted_db)
        ).as_payload()

        clear_session_caches()
        stopped = prepare_quiet_interval(source_db)
        process = artifact["process"]
        stopped.bind_participant_artifacts(
            "gym-afternoon-mara",
            adapter_id=process["adapter"]["id"],
            adapter_version=process["adapter"]["version"],
            model_id=process["model"]["id"],
            private_state=artifact["descriptor"],
        )
        checkpoint = json.loads(json.dumps(stopped.checkpoint()))

        descriptor_path = tmp_path / "descriptor.json"
        process_path = tmp_path / "process.json"
        descriptor_path.write_text(json.dumps(artifact["descriptor"]), encoding="utf-8")
        process_path.write_text(json.dumps(process), encoding="utf-8")
        resident_restore = _agent_artifact_command(
            "restore",
            "--package",
            str(tmp_path / "resident.wwhearth"),
            "--home",
            str(tmp_path / "restored-resident"),
            "--descriptor",
            str(descriptor_path),
            "--expected-process",
            str(process_path),
        )
        assert resident_restore["artifact_id"] == artifact["descriptor"]["artifact_id"]
        assert resident_restore["private_activity"]["open"] is True
        assert "synthetic blue" not in json.dumps(resident_restore)

        resumed = ProductionRuleGym.from_checkpoint(target_db, checkpoint)
        restarted = finish_quiet_interval(resumed).as_payload()

        assert restarted == uninterrupted
        mara_binding = next(
            participant
            for participant in checkpoint["participants"]
            if participant["session_id"] == "gym-afternoon-mara"
        )
        assert mara_binding["private_state"] == artifact["descriptor"]
    finally:
        _close(uninterrupted_engine, uninterrupted_db)
        _close(source_engine, source_db)
        _close(target_engine, target_db)


def test_due_private_return_is_processed_once_across_lost_ack_and_restart(tmp_path):
    source_engine, source_db = _memory_session()
    first_engine, first_db = _memory_session()
    replay_engine, replay_db = _memory_session()
    try:
        artifact = _agent_artifact_command(
            "create-fixture",
            "--home",
            str(tmp_path / "source-resident"),
            "--package",
            str(tmp_path / "resident.wwhearth"),
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
        scheduled_return = artifact["scheduled_return"]
        assert scheduled_return["event_kind"] == "resident_private_return"

        clear_session_caches()
        stopped = prepare_quiet_interval(
            source_db,
            mara_implementation="reference_resident_scripted_wait",
        )
        process = artifact["process"]
        stopped.bind_participant_artifacts(
            "gym-afternoon-mara",
            adapter_id=process["adapter"]["id"],
            adapter_version=process["adapter"]["version"],
            model_id=process["model"]["id"],
            private_state=artifact["descriptor"],
        )
        stopped.schedule_resident_return(
            "gym-afternoon-mara",
            resident_event_id=scheduled_return["event_id"],
            activity_id=scheduled_return["activity_id"],
            due_at=datetime.fromisoformat(scheduled_return["due_at"]),
        )
        checkpoint = json.loads(json.dumps(stopped.checkpoint()))
        assert len(checkpoint["scheduler"]["pending"]) == 3

        descriptor_path = tmp_path / "descriptor.json"
        process_path = tmp_path / "process.json"
        scene_path = tmp_path / "scene.json"
        descriptor_path.write_text(json.dumps(artifact["descriptor"]), encoding="utf-8")
        process_path.write_text(json.dumps(process), encoding="utf-8")
        _agent_artifact_command(
            "restore",
            "--package",
            str(tmp_path / "resident.wwhearth"),
            "--home",
            str(tmp_path / "restored-resident"),
            "--descriptor",
            str(descriptor_path),
            "--expected-process",
            str(process_path),
        )

        resumed = ProductionRuleGym.from_checkpoint(first_db, checkpoint)
        inspection = resumed.offer_next_scheduled()
        assert [event.kind for event in inspection] == ["inspect_sublocation"]
        resumed.inspect_sublocation(
            parent_location=str(inspection[0].payload["parent_location"]),
            sublocation_id=str(inspection[0].payload["sublocation_id"]),
        )
        resumed.acknowledge_scheduled((inspection[0].event_id,))

        due = resumed.offer_next_scheduled()
        assert [event.kind for event in due] == ["resident_private_return"]

        def handle_return(event, scene):
            scene_path.write_text(json.dumps(scene), encoding="utf-8")
            return _agent_artifact_command(
                "handle-return",
                "--home",
                str(tmp_path / "restored-resident"),
                "--expected-process",
                str(process_path),
                "--scene",
                str(scene_path),
                "--event-id",
                str(event.payload["resident_event_id"]),
                "--now",
                event.due_at.isoformat(),
            )

        first_result = resumed.deliver_resident_return(due[0], handle_return)
        assert first_result["status"] == "processed"
        assert first_result["choice"] == "wait"
        assert first_result["model_call_count"] == 1

        # Simulate the engine dying after the resident committed its receipt but
        # before the scheduler acknowledgement reached durable storage.
        lost_ack_checkpoint = json.loads(json.dumps(resumed.checkpoint()))
        assert any(
            item["event_id"] == due[0].event_id
            for item in lost_ack_checkpoint["scheduler"]["pending"]
        )

        replayed = ProductionRuleGym.from_checkpoint(replay_db, lost_ack_checkpoint)
        retried = replayed.offer_next_scheduled()
        assert [event.event_id for event in retried] == [due[0].event_id]
        second_result = replayed.deliver_resident_return(retried[0], handle_return)
        assert second_result["status"] == "already_processed"
        assert second_result["model_call_count"] == 0
        replayed.acknowledge_scheduled((retried[0].event_id,))

        final_inspection = replayed.offer_next_scheduled()
        assert [event.kind for event in final_inspection] == ["inspect_sublocation"]
        replayed.inspect_sublocation(
            parent_location=str(final_inspection[0].payload["parent_location"]),
            sublocation_id=str(final_inspection[0].payload["sublocation_id"]),
        )
        replayed.acknowledge_scheduled((final_inspection[0].event_id,))
        assert replayed.scheduled_checkpoint()["pending"] == []

        lifecycle = [
            record
            for record in replayed.result().records
            if record.kind
            in {
                "observation_ready",
                "resident_activation_started",
                "resident_activation_finished",
            }
        ]
        assert [record.kind for record in lifecycle[-3:]] == [
            "observation_ready",
            "resident_activation_started",
            "resident_activation_finished",
        ]
        assert lifecycle[-1].detail["status"] == "already_processed"
        assert "synthetic blue" not in json.dumps(
            [record.detail for record in lifecycle]
        )
    finally:
        _close(source_engine, source_db)
        _close(first_engine, first_db)
        _close(replay_engine, replay_db)
