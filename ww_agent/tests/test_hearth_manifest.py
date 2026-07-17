from __future__ import annotations

import json

import pytest

from src.identity.hearth_manifest import (
    HEARTH_MANIFEST_FILENAME,
    HearthManifestError,
    initialize_hearth_manifest,
    inspect_hearth_manifest,
    load_hearth_manifest,
    manifest_path,
)


def _resident_home(tmp_path, *, actor_id: str = "actor-123"):
    home = tmp_path / "resident"
    identity = home / "identity"
    identity.mkdir(parents=True)
    (identity / "resident_id.txt").write_text(f"{actor_id}\n", encoding="utf-8")
    return home


def test_inspection_of_legacy_home_is_read_only_and_proposes_stable_identity(tmp_path):
    home = _resident_home(tmp_path)

    report = inspect_hearth_manifest(home)

    assert report["status"] == "missing"
    assert report["proposed_manifest"] == {
        "schema": "worldweaver.hearth",
        "schema_version": 1,
        "actor_id": "actor-123",
        "hearth_shard_id": "hearth:actor-123",
        "runtime_generation": 1,
    }
    assert not manifest_path(home).exists()


def test_explicit_initialization_writes_only_host_independent_fields(tmp_path):
    home = _resident_home(tmp_path)
    (home / "session_id.txt").write_text("city-session", encoding="utf-8")

    initialized = initialize_hearth_manifest(home)
    loaded = load_hearth_manifest(home)
    raw = json.loads(manifest_path(home).read_text(encoding="utf-8"))

    assert loaded == initialized
    assert raw == initialized.to_dict()
    assert set(raw) == {
        "schema",
        "schema_version",
        "actor_id",
        "hearth_shard_id",
        "runtime_generation",
    }
    assert "host" not in raw
    assert "session" not in raw
    assert "current_shard" not in raw


def test_manifest_actor_must_match_resident_identity(tmp_path):
    home = _resident_home(tmp_path)
    initialize_hearth_manifest(home)
    (home / "identity" / "resident_id.txt").write_text(
        "different-actor\n", encoding="utf-8"
    )

    with pytest.raises(HearthManifestError, match="does not match"):
        load_hearth_manifest(home)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", 2, "schema_version"),
        ("runtime_generation", 0, "greater than zero"),
        ("hearth_shard_id", "hearth:someone-else", "hearth_shard_id"),
    ],
)
def test_manifest_rejects_incompatible_identity_or_generation(
    tmp_path, field, value, message
):
    home = _resident_home(tmp_path)
    initialize_hearth_manifest(home)
    path = home / "identity" / HEARTH_MANIFEST_FILENAME
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw[field] = value
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(HearthManifestError, match=message):
        load_hearth_manifest(home)


def test_initialization_refuses_to_replace_an_existing_manifest(tmp_path):
    home = _resident_home(tmp_path)
    initialize_hearth_manifest(home)

    with pytest.raises(HearthManifestError, match="refusing to replace"):
        initialize_hearth_manifest(home)


def test_home_without_durable_actor_identity_is_invalid_not_merely_legacy(tmp_path):
    home = tmp_path / "resident"
    (home / "identity").mkdir(parents=True)

    report = inspect_hearth_manifest(home)

    assert report["status"] == "invalid"
    assert report["error"] == "identity/resident_id.txt is missing"
