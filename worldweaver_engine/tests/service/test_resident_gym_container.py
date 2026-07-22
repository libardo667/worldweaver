# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def test_gym_image_contains_both_production_packages_without_local_secrets():
    workspace = Path(__file__).resolve().parents[3]
    dockerfile = (workspace / "Dockerfile.gym").read_text(encoding="utf-8")
    dockerignore = (workspace / ".dockerignore").read_text(encoding="utf-8")

    assert "COPY worldweaver_engine" in dockerfile
    assert "COPY ww_agent" in dockerfile
    assert 'ENTRYPOINT ["python", "scripts/resident_gym.py"]' in dockerfile
    assert "worldweaver_engine/.env" in dockerignore
    assert "ww_agent/.env" in dockerignore
    assert "ww_agent/residents" in dockerignore


@pytest.mark.skipif(
    os.environ.get("WW_RUN_CONTAINER_TESTS") != "1",
    reason="set WW_RUN_CONTAINER_TESTS=1 for the Docker acceptance proof",
)
def test_model_path_repeats_inside_disposable_container(tmp_path):
    workspace = Path(__file__).resolve().parents[3]
    output = tmp_path / "model-container.html"
    completed = subprocess.run(
        [
            sys.executable,
            "dev.py",
            "gym",
            "--container",
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
        cwd=workspace,
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )

    assert completed.returncode == 0, completed.stderr
    json_start = completed.stdout.find('{\n  "schema"')
    json_end = completed.stdout.find("\nVisual episode:", json_start)
    assert json_start >= 0 and json_end > json_start, completed.stdout
    payload = json.loads(completed.stdout[json_start:json_end])
    assert payload["schema_version"] == 10
    assert payload["fidelity"]["infrastructure"] == "disposable_container"
    assert payload["fidelity"]["participant_transport"] == (
        "worldweaver_client_http_via_loopback"
    )
    assert payload["final_locations"]["Mara"] == "the hearth"
    assert output.is_file()

    image_check = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--entrypoint",
            "sh",
            "worldweaver-resident-gym:dev",
            "-c",
            "test ! -e /workspace/ww_agent/.env"
            " && test ! -e /workspace/worldweaver_engine/.env"
            " && test ! -e /workspace/ww_agent/residents",
        ],
        text=True,
        capture_output=True,
        check=False,
        timeout=60,
    )
    assert image_check.returncode == 0, image_check.stderr
