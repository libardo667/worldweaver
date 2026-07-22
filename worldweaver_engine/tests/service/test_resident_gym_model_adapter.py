# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

import json
from pathlib import Path
import subprocess
import sys

import pytest


def test_resident_duet_overlaps_two_model_hosts_in_one_shared_shard(tmp_path):
    engine_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "resident-duet.html"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "resident-duet",
            "--transport-mode",
            "loopback",
            "--json",
            "--output",
            str(output),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\nVisual episode:", 1)[0])
    records = payload["records"]
    concurrency = [
        record
        for record in records
        if record["kind"] == "resident_concurrency_verified"
    ]
    later_speech = [
        record
        for record in records
        if record["kind"] == "participant_speech_ready"
        and record["occurred_at"] == "2026-07-21T18:01:00+00:00"
    ]
    attachments = [
        record for record in records if record["kind"] == "resident_attachment_verified"
    ]

    assert payload["episode"] == "Two Voices at the Worktable"
    assert [item["display_name"] for item in payload["participants"]] == [
        "Mara",
        "Ivo",
    ]
    assert all(
        item["implementation"] == "reference_resident_model"
        for item in payload["participants"]
    )
    assert payload["final_locations"] == {
        "Mara": "Commons Worktable",
        "Ivo": "Commons Worktable",
    }
    assert [record["detail"]["wave"] for record in concurrency] == [0, 1]
    assert all(record["detail"]["resident_count"] == 2 for record in concurrency)
    assert all(record["detail"]["process_count"] == 2 for record in concurrency)
    assert len(later_speech) >= 2
    assert {record["actor"] for record in later_speech} == {"Mara", "Ivo"}
    assert all(record["detail"]["message_count"] == 2 for record in later_speech)
    assert len(attachments) == 2
    assert all(
        record["detail"]
        == {
            "attachment": "city",
            "process_hosting_state": "suspended",
            "active_city_session_count": 1,
        }
        for record in attachments
    )
    chronology = next(
        record for record in records if record["kind"] == "world_chronology_audited"
    )
    assert chronology["detail"]["row_counts"]["location_chat"] == 2
    assert chronology["detail"]["off_clock_count"] == 0
    assert output.is_file()


def test_counterfactual_fork_restores_one_checkpoint_and_private_artifact_twice(
    tmp_path,
):
    engine_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "forked-invitation.html"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "willow-fork",
            "--model",
            "test/gym-fork-v1",
            "--model-mode",
            "scripted-read-move",
            "--transport-mode",
            "loopback",
            "--json",
            "--output",
            str(output),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\nVisual episode:", 1)[0])
    assert payload["schema"] == "worldweaver.resident-gym.counterfactual"
    assert payload["schema_version"] == 1
    assert payload["source_checkpoint_id"]
    assert payload["private_artifact_id"]
    assert payload["invariants"] == {
        "same_engine_checkpoint": True,
        "same_private_artifact": True,
        "independent_engine_databases": True,
        "independent_resident_homes": True,
        "one_declared_intervention": True,
    }
    assert [branch["branch_id"] for branch in payload["branches"]] == [
        "invitation",
        "quiet",
    ]
    invitation, quiet = payload["branches"]
    for branch in (invitation, quiet):
        assert branch["summary"]["model_calls"] == 2
        assert branch["summary"]["attachment"] == "city"
        assert branch["summary"]["final_location"] == "Footbridge"
        assert branch["summary"]["off_clock_rows"] == 0
        assert branch["episode"]["records"][: payload["common_record_count"]] == (
            invitation["episode"]["records"][: payload["common_record_count"]]
        )

    invitation_speech = next(
        record
        for record in invitation["episode"]["records"]
        if record["kind"] == "participant_speech_ready"
    )
    quiet_speech = next(
        record
        for record in quiet["episode"]["records"]
        if record["kind"] == "participant_speech_ready"
    )
    assert invitation_speech["detail"]["message_count"] == (
        quiet_speech["detail"]["message_count"] + 1
    )
    assert "synthetic blue" not in completed.stdout
    assert output.is_file()


def test_two_way_model_adapter_reads_then_returns_home_through_production_rules(
    tmp_path,
):
    engine_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "model-appointment.html"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "resident-model",
            "--model",
            "test/gym-read-home-v1",
            "--model-mode",
            "scripted-read-home",
            "--json",
            "--output",
            str(output),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\nVisual episode:", 1)[0])
    records = payload["records"]

    assert payload["schema_version"] == 10
    assert payload["final_locations"]["Mara"] == "the hearth"
    assert payload["fidelity"] == {
        "engine_rules": "production_fastapi_routes_and_services",
        "infrastructure": "host_process",
        "world_state": "synthetic_sqlite",
        "resident_composition": "normal_resident_host_and_reference_core",
        "participant_transport": "worldweaver_client_http_via_stdio",
        "resident_authorization": "signed_runtime_certificate",
        "city_sources": "node_published_then_local_world_registry",
        "world_time": "controlled_clock_across_engine_and_resident_world_state",
        "hearth_attachment": "local_world_city_to_hearth_restart",
        "federation": "not_exercised",
    }
    assert [record["kind"] for record in records].count(
        "resident_inference_started"
    ) == 2
    assert [record["kind"] for record in records].count(
        "resident_inference_finished"
    ) == 2
    assert [record["kind"] for record in records].count("resident_host_started") == 2
    assert [record["kind"] for record in records].count("resident_host_finished") == 2
    assert any(
        record["kind"] == "resident_city_profile_loaded"
        and record["detail"]
        == {
            "city_id": "resident_gym",
            "capability_ids": [],
            "source_names": ["measure", "places", "recall", "travel"],
        }
        for record in records
    )
    attachment = next(
        record for record in records if record["kind"] == "resident_attachment_verified"
    )
    assert attachment["location"] == "the hearth"
    assert attachment["detail"] == {
        "attachment": "hearth",
        "process_hosting_state": "suspended",
        "active_city_session_count": 0,
    }
    hearth = next(
        record for record in records if record["kind"] == "resident_hearth_observed"
    )
    assert hearth["occurred_at"] == "2026-07-22T12:00:00+00:00"
    assert hearth["location"] == "the hearth"
    assert hearth["detail"]["attachment"] == "hearth"
    assert hearth["detail"]["hosting_state"] == "hosted"
    assert hearth["detail"]["source_names"] == ["growth", "measure", "recall"]
    assert "places" not in hearth["detail"]["source_names"]
    assert "travel" not in hearth["detail"]["source_names"]
    assert hearth["detail"]["observed_at"] == "2026-07-22T12:00:00+00:00"
    http_records = [
        record for record in records if record["kind"] == "participant_http"
    ]
    assert any(
        record["detail"]
        == {
            "method": "GET",
            "path": "/api/settings/readiness",
            "status_code": 200,
            "resident_proof": False,
        }
        for record in http_records
    )
    for path in (
        "/api/shard/experience",
        "/api/shard/city-pack/preview",
        "/api/world/scene/gym-afternoon-mara",
        "/api/session/leave",
    ):
        assert any(
            record["detail"]["path"] == path
            and record["detail"]["status_code"] == 200
            and record["detail"]["resident_proof"] is True
            for record in http_records
        )
    leave_sequence = next(
        record["sequence"]
        for record in http_records
        if record["detail"]["path"] == "/api/session/leave"
    )
    assert {
        record["detail"]["path"]
        for record in http_records
        if record["sequence"] > leave_sequence
    } == {"/api/settings/readiness"}
    direct_scene = next(
        record for record in records if record["kind"] == "observation_ready"
    )
    http_scene = next(
        record for record in records if record["kind"] == "participant_scene_ready"
    )
    assert http_scene["occurred_at"] == direct_scene["occurred_at"]
    assert http_scene["location"] == direct_scene["location"] == "Willow Court"
    assert http_scene["detail"] == direct_scene["detail"]
    assert http_scene["detail"]["place_count"] == 2
    chronology = next(
        record for record in records if record["kind"] == "world_chronology_audited"
    )
    assert chronology["occurred_at"] == "2026-07-22T12:00:00+00:00"
    assert chronology["detail"]["off_clock_count"] == 0
    assert chronology["detail"]["instants"] == [
        "2026-07-20T12:00:00+00:00",
        "2026-07-22T12:00:00+00:00",
    ]
    assert chronology["detail"]["row_counts"]["resident_retirement_receipt"] == 1
    assert chronology["detail"]["row_counts"]["world_event"] == 3
    assert chronology["detail"]["row_counts"]["location_chat"] == 1
    assert "6 * 7" not in completed.stdout
    assert "synthetic blue" not in completed.stdout
    assert output.is_file()


@pytest.mark.parametrize(
    ("fault", "leave_statuses", "receipt_count"),
    (
        ("before_request", [200], 1),
        ("before_commit", [500, 200], 1),
        ("response_loss", [200, 200], 2),
        ("after_hearth_checkpoint", [200], 1),
    ),
)
def test_model_resident_departure_recovers_once_across_each_failure_boundary(
    tmp_path,
    fault,
    leave_statuses,
    receipt_count,
):
    engine_root = Path(__file__).resolve().parents[2]
    output = tmp_path / f"model-appointment-{fault}.html"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "resident-model",
            "--model",
            "test/gym-read-home-v1",
            "--model-mode",
            "scripted-read-home",
            "--departure-fault",
            fault,
            "--json",
            "--output",
            str(output),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\nVisual episode:", 1)[0])
    records = payload["records"]
    kinds = [record["kind"] for record in records]

    assert payload["final_locations"]["Mara"] == "the hearth"
    assert kinds.count("resident_inference_started") == 2
    assert kinds.count("resident_inference_finished") == 2
    assert kinds.count("resident_host_started") == 2
    assert kinds.count("resident_attachment_checkpointed") == 1
    assert kinds.count("resident_hearth_observed") == 1
    assert kinds.count("resident_attachment_verified") == 1
    fault_record = next(
        record
        for record in records
        if record["kind"] == "resident_departure_fault_injected"
    )
    assert fault_record["detail"] == {"mode": fault}

    leave_http = [
        record
        for record in records
        if record["kind"] == "participant_http"
        and record["detail"]["path"] == "/api/session/leave"
    ]
    assert [record["detail"]["status_code"] for record in leave_http] == leave_statuses
    receipts = [
        record for record in records if record["kind"] == "resident_departure_receipt"
    ]
    assert len(receipts) == receipt_count
    if fault == "response_loss":
        assert receipts[0]["detail"] == receipts[1]["detail"]

    checkpoint = next(
        record
        for record in records
        if record["kind"] == "resident_attachment_checkpointed"
    )
    assert all(
        receipt["detail"]["transition_id"] == checkpoint["detail"]["transition_id"]
        for receipt in receipts
    )
    verified = next(
        record for record in records if record["kind"] == "resident_attachment_verified"
    )
    assert verified["detail"] == {
        "attachment": "hearth",
        "process_hosting_state": "suspended",
        "active_city_session_count": 0,
    }
    assert output.is_file()


@pytest.mark.parametrize(
    ("fault", "error_fragment"),
    (
        ("child_exit", "resident adapter stopped without a result"),
        ("malformed_json", "resident adapter emitted invalid JSON"),
        ("malformed_message", "resident adapter emitted an unknown message"),
        ("replayed_request", "resident adapter replayed or omitted a request ID"),
        ("malformed_response", "gym adapter returned invalid JSON"),
    ),
)
def test_model_adapter_fails_closed_on_child_and_transport_faults(
    tmp_path,
    fault,
    error_fragment,
):
    engine_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "resident-model",
            "--model",
            "test/gym-read-home-v1",
            "--model-mode",
            "scripted-read-home",
            "--transport-fault",
            fault,
            "--json",
            "--output",
            str(tmp_path / f"transport-{fault}.html"),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode != 0
    assert error_fragment in completed.stderr
    assert not (tmp_path / f"transport-{fault}.html").exists()


def test_model_resident_transition_crosses_a_real_loopback_server(tmp_path):
    engine_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "model-appointment-loopback.html"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "resident-model",
            "--model",
            "test/gym-read-home-v1",
            "--model-mode",
            "scripted-read-home",
            "--transport-mode",
            "loopback",
            "--json",
            "--output",
            str(output),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\nVisual episode:", 1)[0])
    records = payload["records"]
    kinds = [record["kind"] for record in records]

    assert payload["fidelity"]["participant_transport"] == (
        "worldweaver_client_http_via_loopback"
    )
    assert payload["final_locations"]["Mara"] == "the hearth"
    assert kinds.count("resident_loopback_transport_started") == 1
    assert kinds.count("resident_inference_started") == 2
    assert kinds.count("resident_attachment_checkpointed") == 1
    assert kinds.count("resident_hearth_observed") == 1
    assert kinds.count("resident_departure_receipt") == 1
    leave = next(
        record
        for record in records
        if record["kind"] == "participant_http"
        and record["detail"]["path"] == "/api/session/leave"
    )
    assert leave["detail"] == {
        "method": "POST",
        "path": "/api/session/leave",
        "status_code": 200,
        "resident_proof": True,
    }
    verified = next(
        record for record in records if record["kind"] == "resident_attachment_verified"
    )
    assert verified["detail"]["active_city_session_count"] == 0
    assert verified["detail"]["process_hosting_state"] == "suspended"
    assert output.is_file()


def test_model_runner_accepts_a_valid_suspended_city_outcome(tmp_path):
    engine_root = Path(__file__).resolve().parents[2]
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "resident-model",
            "--model",
            "test/gym-read-move-v1",
            "--model-mode",
            "scripted-read-move",
            "--transport-mode",
            "loopback",
            "--json",
            "--output",
            str(tmp_path / "model-city-outcome.html"),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\nVisual episode:", 1)[0])
    verified = next(
        record
        for record in payload["records"]
        if record["kind"] == "resident_attachment_verified"
    )
    assert payload["final_locations"]["Mara"] == "Footbridge"
    assert payload["fidelity"]["city_sources"] == "node_published_city_registry"
    assert payload["fidelity"]["hearth_attachment"] == "city_attachment_retained"
    assert verified["detail"] == {
        "attachment": "city",
        "process_hosting_state": "suspended",
        "active_city_session_count": 1,
    }
    assert all(
        record["kind"] != "resident_departure_receipt" for record in payload["records"]
    )


def test_willow_week_runs_six_host_intervals_across_seven_controlled_days(tmp_path):
    engine_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "willow-week.html"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "willow-week",
            "--model",
            "test/willow-week-v1",
            "--model-mode",
            "scripted-week",
            "--transport-mode",
            "loopback",
            "--json",
            "--output",
            str(output),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\nVisual episode:", 1)[0])
    records = payload["records"]
    kinds = [record["kind"] for record in records]
    activations = [
        record for record in records if record["kind"] == "resident_activation_finished"
    ]

    assert payload["episode"] == "Willow Week"
    assert payload["final_locations"]["Mara"] == "the hearth"
    assert [record["detail"]["choice"] for record in activations] == [
        "act",
        "act",
        "wait",
        "wait",
        "act",
        "act",
    ]
    assert [record["detail"]["model_call_count"] for record in activations] == [
        1,
        1,
        1,
        1,
        2,
        1,
    ]
    assert kinds.count("resident_inference_finished") == 7
    assert kinds.count("letter_sent") == 2
    assert kinds.count("resident_departure_receipt") == 1
    assert kinds.count("resident_hearth_observed") == 1
    assert kinds.count("resident_attachment_verified") == 1
    assert (
        sum(
            record["detail"]["elapsed_seconds"]
            for record in records
            if record["kind"] == "time_advanced"
        )
        == 7 * 24 * 60 * 60
    )
    chronology = next(
        record for record in records if record["kind"] == "world_chronology_audited"
    )
    assert chronology["detail"]["off_clock_count"] == 0
    assert chronology["detail"]["row_counts"]["direct_message_sent"] == 2
    assert chronology["detail"]["row_counts"]["direct_message_acknowledged"] == 2
    verified = next(
        record for record in records if record["kind"] == "resident_attachment_verified"
    )
    assert verified["detail"] == {
        "attachment": "hearth",
        "process_hosting_state": "suspended",
        "active_city_session_count": 0,
    }
    assert output.is_file()


def test_material_day_uses_resident_effectors_receipts_refusal_and_hearth_gift(
    tmp_path,
):
    engine_root = Path(__file__).resolve().parents[2]
    output = tmp_path / "commons-worktable.html"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym.py",
            "--episode",
            "material-day",
            "--transport-mode",
            "loopback",
            "--json",
            "--output",
            str(output),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout.split("\nVisual episode:", 1)[0])
    records = payload["records"]
    material = next(
        record
        for record in records
        if record["kind"] == "material_capabilities_audited"
    )["detail"]
    hearth = next(
        record for record in records if record["kind"] == "resident_hearth_observed"
    )["detail"]
    chronology = next(
        record for record in records if record["kind"] == "world_chronology_audited"
    )["detail"]

    assert payload["episode"] == "The Commons Worktable"
    assert payload["final_locations"] == {
        "Mara": "the hearth",
        "Ivo": "Commons Worktable",
    }
    assert payload["fidelity"]["participant_transport"] == (
        "worldweaver_client_http_via_loopback"
    )
    assert material == {
        "operations": [
            "object_exchange_completed",
            "object_exchange_offered",
            "object_founded",
            "object_given",
            "object_made",
            "space_access_denied",
            "space_access_requested",
            "stoop_object_left",
            "stoop_object_taken",
        ],
        "source_names": ["access", "exchanges", "making", "objects", "stoops"],
        "durable_object_count": 3,
        "material_pool_count": 2,
        "receipt_count": 10,
        "completed_exchange_count": 1,
        "denied_access_request_count": 1,
        "taken_stoop_entry_count": 1,
        "access_refusal_count": 1,
        "duplicate_receipt_count": 0,
        "invalid_attachment_count": 0,
    }
    refusal = next(
        record for record in records if record["kind"] == "participant_access_refused"
    )
    assert refusal["detail"] == {
        "code": "space_access_required",
        "status_code": 403,
    }
    assert hearth["attachment"] == "hearth"
    assert "gifts" in hearth["source_names"]
    assert not {"access", "exchanges", "making", "objects", "stoops"}.intersection(
        hearth["source_names"]
    )
    final_host = [
        record for record in records if record["kind"] == "resident_host_finished"
    ][-1]
    final_inference = [
        record for record in records if record["kind"] == "resident_inference_started"
    ]
    assert final_host["location"] == "the hearth"
    assert final_inference[-1]["sequence"] < next(
        record["sequence"]
        for record in records
        if record["kind"] == "resident_departure_receipt"
    )
    assert chronology["off_clock_count"] == 0
    assert chronology["row_counts"]["durable_object_updated"] == 3
    assert chronology["row_counts"]["material_pool_updated"] == 2
    assert output.is_file()
