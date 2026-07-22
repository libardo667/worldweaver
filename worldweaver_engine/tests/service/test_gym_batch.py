# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

import json
from pathlib import Path
import subprocess
import sys

import pytest

from src.services.gym_batch import GymBatchError, aggregate_batch, summarize_episode


def _payload() -> dict:
    return {
        "schema": "worldweaver.resident-gym.episode",
        "schema_version": 10,
        "episode": "Synthetic batch member",
        "fidelity": {
            "infrastructure": "host_process",
            "participant_transport": "worldweaver_client_http_via_loopback",
        },
        "final_locations": {"Mara": "the hearth"},
        "records": [
            {
                "kind": "resident_inference_started",
                "detail": {"call_index": 1, "model_id": "test/model"},
            },
            {
                "kind": "resident_inference_finished",
                "detail": {
                    "call_index": 1,
                    "model_id": "test/model",
                    "prompt_tokens": 12,
                    "completion_tokens": 3,
                    "private_completion": "must not escape",
                },
            },
            {
                "kind": "resident_inference_started",
                "detail": {"call_index": 2, "model_id": "test/model"},
            },
            {
                "kind": "resident_inference_failed",
                "detail": {
                    "call_index": 2,
                    "model_id": "test/model",
                    "reason": "InferenceError",
                    "prompt_tokens": 20,
                    "completion_tokens": 5,
                },
            },
            {
                "kind": "resident_activation_finished",
                "detail": {"choice": "wait", "activation_status": "completed"},
            },
            {
                "kind": "resident_attachment_verified",
                "detail": {"attachment": "hearth"},
            },
            {"kind": "resident_departure_receipt", "detail": {}},
            {
                "kind": "participant_http",
                "detail": {"status_code": 200, "private_body": "must not escape"},
            },
            {
                "kind": "world_chronology_audited",
                "detail": {"off_clock_count": 0},
            },
        ],
    }


def test_batch_summary_is_structural_and_drops_episode_prose():
    summary = summarize_episode(
        _payload(), run_id="run-0001", duration_ms=42, report_name="run.html"
    )

    assert summary["model_id"] == "test/model"
    assert summary["choice"] == "wait"
    assert summary["attachment"] == "hearth"
    assert summary["model_calls"] == 2
    assert summary["inference_failures"] == 1
    assert summary["prompt_tokens"] == 20
    assert summary["completion_tokens"] == 5
    assert summary["http_refusals"] == 0
    assert summary["http_server_errors"] == 0
    assert "must not escape" not in json.dumps(summary)

    aggregate = aggregate_batch(
        [summary],
        [],
        requested_runs=1,
        models=["test/model"],
        concurrency=1,
        transport="loopback",
        infrastructure="host_process",
        episode="resident-model",
    )
    assert aggregate["totals"]["completed_runs"] == 1
    assert aggregate["configuration"]["episode"] == "resident-model"
    assert aggregate["totals"]["model_calls"] == 2
    assert aggregate["totals"]["inference_failures"] == 1
    assert aggregate["totals"]["http_refusals"] == 0
    assert aggregate["totals"]["http_server_errors"] == 0
    assert aggregate["distributions"]["choices"] == {"wait": 1}
    assert aggregate["distributions"]["failure_classes"] == {}


def test_batch_summary_distinguishes_refusals_from_server_errors():
    payload = _payload()
    payload["records"].extend(
        [
            {"kind": "participant_http", "detail": {"status_code": 422}},
            {"kind": "participant_http", "detail": {"status_code": 503}},
        ]
    )

    summary = summarize_episode(
        payload, run_id="run-http", duration_ms=1, report_name="run.html"
    )

    assert summary["http_errors"] == 2
    assert summary["http_refusals"] == 1
    assert summary["http_server_errors"] == 1


def test_batch_summary_refuses_an_inference_attempt_without_a_terminal_boundary():
    payload = _payload()
    payload["records"].append(
        {
            "kind": "resident_inference_started",
            "detail": {"call_index": 3, "model_id": "test/model"},
        }
    )

    with pytest.raises(GymBatchError, match="no terminal boundary"):
        summarize_episode(
            payload, run_id="run-dangling", duration_ms=1, report_name="run.html"
        )


def test_episode_failure_envelope_is_bounded_and_contains_no_exception_message(
    tmp_path,
):
    engine_root = Path(__file__).resolve().parents[2]
    failure_path = tmp_path / "failure.json"
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
            "stdio",
            "--transport-fault",
            "child_exit",
            "--failure-output",
            str(failure_path),
            "--no-stream",
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 1
    assert json.loads(failure_path.read_text(encoding="utf-8")) == {
        "episode": "resident-model",
        "exception_type": "RuntimeError",
        "failure_class": "resident_process",
        "schema": "worldweaver.resident-gym.failure",
        "schema_version": 1,
    }


def test_batch_runner_aggregates_independent_model_processes(tmp_path):
    engine_root = Path(__file__).resolve().parents[2]
    output_dir = tmp_path / "batch"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/resident_gym_batch.py",
            "--runs-per-model",
            "3",
            "--concurrency",
            "3",
            "--model",
            "test/gym-read-home-v1",
            "--model-mode",
            "scripted-read-home",
            "--output-dir",
            str(output_dir),
        ],
        cwd=engine_root,
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )

    assert completed.returncode == 0, completed.stderr
    aggregate = json.loads((output_dir / "aggregate.json").read_text(encoding="utf-8"))
    assert aggregate["configuration"]["requested_runs"] == 3
    assert aggregate["totals"]["completed_runs"] == 3
    assert aggregate["totals"]["failed_runs"] == 0
    assert aggregate["totals"]["model_calls"] == 6
    assert aggregate["totals"]["retirement_receipts"] == 3
    assert aggregate["totals"]["http_errors"] == 0
    assert aggregate["totals"]["http_refusals"] == 0
    assert aggregate["totals"]["http_server_errors"] == 0
    assert aggregate["totals"]["off_clock_rows"] == 0
    assert aggregate["distributions"]["attachments"] == {"hearth": 3}
    assert len(list(output_dir.glob("run-*.html"))) == 3
    assert (output_dir / "aggregate.html").is_file()
