# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

import json
from pathlib import Path
import subprocess
import sys


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

    assert payload["schema_version"] == 8
    assert payload["final_locations"]["Mara"] == "the hearth"
    assert payload["fidelity"] == {
        "engine_rules": "production_fastapi_routes_and_services",
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
    assert chronology["detail"]["instants"] == ["2026-07-20T12:00:00+00:00"]
    assert chronology["detail"]["row_counts"]["world_event"] == 3
    assert chronology["detail"]["row_counts"]["location_chat"] == 1
    assert "6 * 7" not in completed.stdout
    assert "synthetic blue" not in completed.stdout
    assert output.is_file()
