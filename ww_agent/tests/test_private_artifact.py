# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Levi Banks

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from src.identity.hearth_manifest import initialize_hearth_manifest
from src.identity.hearth_package import export_hearth_package
from src.runtime.ledger import (
    append_runtime_event,
    load_open_private_activity,
    load_resident_process_envelope,
    load_runtime_checkpoint,
)
from src.runtime.private_artifact import (
    PrivateArtifactError,
    describe_private_artifact,
    restore_private_artifact,
)
from src.runtime.process_state import ResidentProcessBinding


def _private_home(tmp_path: Path) -> tuple[Path, ResidentProcessBinding, str]:
    home = tmp_path / "source-resident"
    identity_dir = home / "identity"
    identity_dir.mkdir(parents=True)
    actor_id = "gym-afternoon-actor-mara"
    (identity_dir / "resident_id.txt").write_text(f"{actor_id}\n", encoding="utf-8")
    manifest = initialize_hearth_manifest(home)
    binding = ResidentProcessBinding(
        actor_id=actor_id,
        hearth_shard_id=manifest.hearth_shard_id,
        runtime_generation=manifest.runtime_generation,
        attachment_kind="city",
        world_id="gym-long-afternoon-world",
        city_id="",
        session_id="gym-afternoon-mara",
        model_id="test/reference-policy-v1",
    )
    memory_dir = home / "memory"
    append_runtime_event(
        memory_dir,
        event_type="reference_process_bound",
        payload=binding.as_dict(),
        ts="2026-07-20T12:00:00+00:00",
    )
    private_activity = "Privately compare the blue and green route notes."
    append_runtime_event(
        memory_dir,
        event_type="reference_activity_continued",
        payload={
            "activity_state_version": 1,
            "activity_id": "activity-route-notes",
            "activity": private_activity,
            "opened_at": "2026-07-20T12:00:00+00:00",
            "return_at": "2026-07-22T12:00:00+00:00",
            "wake_on": ["local_speech"],
        },
        ts="2026-07-20T12:00:00+00:00",
    )
    return home, binding, private_activity


def test_private_artifact_restores_ledger_and_process_without_reporting_prose(
    tmp_path,
):
    source, binding, private_activity = _private_home(tmp_path)
    package = tmp_path / "resident.wwhearth"
    export_hearth_package(source, package)
    descriptor = describe_private_artifact(package)

    target = tmp_path / "restored-resident"
    report = restore_private_artifact(
        package,
        target,
        descriptor=descriptor.as_dict(),
        expected_process=binding,
    )

    assert report["artifact_id"] == descriptor.artifact_id
    assert report["actor_id"] == binding.actor_id
    assert report["private_activity"] == {
        "open": True,
        "activity_id": "activity-route-notes",
        "return_at": "2026-07-22T12:00:00+00:00",
        "wake_on": ["local_speech"],
    }
    assert private_activity not in json.dumps(descriptor.as_dict())
    assert private_activity not in json.dumps(report)

    memory_dir = target / "memory"
    assert load_runtime_checkpoint(memory_dir) is not None
    assert load_resident_process_envelope(memory_dir) is not None
    assert load_open_private_activity(memory_dir)["activity"] == private_activity


def test_private_artifact_rejects_changed_bytes_before_creating_a_home(tmp_path):
    source, binding, _private_activity = _private_home(tmp_path)
    package = tmp_path / "resident.wwhearth"
    export_hearth_package(source, package)
    descriptor = describe_private_artifact(package)
    package.write_bytes(package.read_bytes() + b"changed")
    target = tmp_path / "rejected-resident"

    with pytest.raises(PrivateArtifactError, match="integrity"):
        restore_private_artifact(
            package,
            target,
            descriptor=descriptor,
            expected_process=binding,
        )

    assert not target.exists()
    assert not list(tmp_path.glob(".rejected-resident.private-artifact.*"))


def test_private_artifact_rejects_a_different_process_before_install(tmp_path):
    source, binding, _private_activity = _private_home(tmp_path)
    package = tmp_path / "resident.wwhearth"
    export_hearth_package(source, package)
    descriptor = describe_private_artifact(package)
    wrong_session = replace(binding, session_id="somebody-elses-session")
    target = tmp_path / "rejected-resident"

    with pytest.raises(PrivateArtifactError, match="process binding"):
        restore_private_artifact(
            package,
            target,
            descriptor=descriptor,
            expected_process=wrong_session,
        )

    assert not target.exists()
    assert not list(tmp_path.glob(".rejected-resident.private-artifact.*"))
