from __future__ import annotations

import json
import zipfile

import pytest

from src.identity.hearth_package import (
    HEARTH_PACKAGE_METADATA,
    HearthPackageError,
    classify_hearth_path,
    export_hearth_package,
    import_hearth_package,
    inventory_hearth,
)
from src.identity.hearth_manifest import initialize_hearth_manifest


def _home(tmp_path):
    home = tmp_path / "resident"
    (home / "identity").mkdir(parents=True)
    (home / "identity" / "resident_id.txt").write_text("actor-123\n", encoding="utf-8")
    initialize_hearth_manifest(home)
    return home


def test_classification_keeps_identity_and_ledger_but_excludes_session_and_host_grants():
    assert classify_hearth_path("identity/resident_id.txt")[0] == "portable"
    assert classify_hearth_path("memory/runtime_ledger.jsonl")[0] == "portable"
    assert classify_hearth_path("workshop/journal.md")[0] == "portable"
    assert classify_hearth_path("memory/runtime_projection.json")[0] == "rebuildable"
    assert classify_hearth_path("session_id.txt")[0] == "city_local"
    assert classify_hearth_path("identity/entry_location.txt")[0] == "city_local"
    assert classify_hearth_path("hearth.json")[0] == "host_specific"


def test_credentials_are_excluded_even_inside_otherwise_portable_directories():
    assert classify_hearth_path("workshop/api_token.txt")[0] == "host_specific"
    assert classify_hearth_path("memory/private_key.pem")[0] == "host_specific"
    assert classify_hearth_path("identity/.env")[0] == "host_specific"


def test_unknown_paths_and_symlinks_block_packaging(tmp_path):
    home = _home(tmp_path)
    (home / "mystery.bin").write_bytes(b"unknown")
    (home / "workshop").mkdir()
    (home / "workshop" / "outside").symlink_to(tmp_path / "elsewhere")

    inventory = inventory_hearth(home)
    by_path = {item.path: item for item in inventory.items}

    assert by_path["mystery.bin"].disposition == "unknown"
    assert by_path["workshop/outside"].disposition == "unknown"
    assert inventory.blocked is True


def test_inventory_is_sorted_deterministic_and_hashes_only_portable_files(tmp_path):
    home = _home(tmp_path)
    (home / "memory").mkdir()
    (home / "memory" / "runtime_ledger.jsonl").write_text(
        '{"event":"one"}\n', encoding="utf-8"
    )
    (home / "memory" / "runtime_projection.json").write_text("{}\n", encoding="utf-8")
    (home / "session_id.txt").write_text("city-session\n", encoding="utf-8")
    (home / "hearth.json").write_text(
        json.dumps({"read_roots": ["shared"]}), encoding="utf-8"
    )

    first = inventory_hearth(home)
    second = inventory_hearth(home)

    assert first.to_dict() == second.to_dict()
    assert [item.path for item in first.items] == sorted(
        item.path for item in first.items
    )
    by_path = {item.path: item for item in first.items}
    assert by_path["memory/runtime_ledger.jsonl"].sha256
    assert by_path["memory/runtime_projection.json"].sha256 is None
    assert by_path["session_id.txt"].sha256 is None
    assert first.blocked is False


def _populated_home(tmp_path):
    home = _home(tmp_path)
    (home / "memory").mkdir()
    (home / "memory" / "runtime_ledger.jsonl").write_text(
        '{"event":"one"}\n', encoding="utf-8"
    )
    (home / "memory" / "runtime_projection.json").write_text("{}\n", encoding="utf-8")
    (home / "workshop").mkdir()
    (home / "workshop" / "note.md").write_text("resident note\n", encoding="utf-8")
    (home / "session_id.txt").write_text("city-session\n", encoding="utf-8")
    (home / "hearth.json").write_text(
        json.dumps({"read_roots": ["/host/path"]}), encoding="utf-8"
    )
    return home


def test_export_is_deterministic_and_import_restores_only_portable_state(tmp_path):
    home = _populated_home(tmp_path)
    first = tmp_path / "first.wwhearth"
    second = tmp_path / "second.wwhearth"

    first_report = export_hearth_package(home, first)
    second_report = export_hearth_package(home, second)

    assert first.read_bytes() == second.read_bytes()
    assert first_report == second_report
    assert [record["path"] for record in first_report["files"]] == sorted(
        record["path"] for record in first_report["files"]
    )

    imported = tmp_path / "imported"
    import_report = import_hearth_package(first, imported)

    assert import_report == first_report
    assert (imported / "identity" / "resident_id.txt").read_text() == "actor-123\n"
    assert (imported / "memory" / "runtime_ledger.jsonl").is_file()
    assert (imported / "workshop" / "note.md").is_file()
    assert not (imported / "memory" / "runtime_projection.json").exists()
    assert not (imported / "session_id.txt").exists()
    assert not (imported / "hearth.json").exists()


def test_export_requires_initialized_manifest_and_rejects_unknown_paths(tmp_path):
    missing_manifest = tmp_path / "legacy"
    (missing_manifest / "identity").mkdir(parents=True)
    (missing_manifest / "identity" / "resident_id.txt").write_text(
        "legacy-actor\n", encoding="utf-8"
    )
    with pytest.raises(HearthPackageError, match="manifest.*missing"):
        export_hearth_package(missing_manifest, tmp_path / "legacy.wwhearth")

    home = _home(tmp_path / "other")
    (home / "mystery.bin").write_bytes(b"unknown")
    with pytest.raises(HearthPackageError, match="mystery.bin"):
        export_hearth_package(home, tmp_path / "unknown.wwhearth")


def test_import_rejects_tampering_without_leaving_a_partial_home(tmp_path):
    home = _populated_home(tmp_path)
    package = tmp_path / "valid.wwhearth"
    export_hearth_package(home, package)

    with zipfile.ZipFile(package, "r") as source:
        members = {name: source.read(name) for name in source.namelist()}
    members["memory/runtime_ledger.jsonl"] = b'{"event":"two"}\n'
    tampered = tmp_path / "tampered.wwhearth"
    with zipfile.ZipFile(tampered, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)

    target = tmp_path / "rejected"
    with pytest.raises(HearthPackageError, match="integrity check"):
        import_hearth_package(tampered, target)
    assert not target.exists()
    assert not list(tmp_path.glob(".rejected.import.*"))


def test_import_rejects_undeclared_or_nonportable_members(tmp_path):
    home = _populated_home(tmp_path)
    package = tmp_path / "valid.wwhearth"
    export_hearth_package(home, package)

    with zipfile.ZipFile(package, "r") as source:
        metadata = json.loads(source.read(HEARTH_PACKAGE_METADATA))
        members = {name: source.read(name) for name in source.namelist()}
    metadata["files"].append(
        {
            "path": "session_id.txt",
            "size": 8,
            "sha256": "0" * 64,
        }
    )
    members[HEARTH_PACKAGE_METADATA] = (
        json.dumps(metadata, indent=2, sort_keys=True) + "\n"
    ).encode()
    members["session_id.txt"] = b"session\n"
    unsafe = tmp_path / "unsafe.wwhearth"
    with zipfile.ZipFile(unsafe, "w") as archive:
        for name, content in members.items():
            archive.writestr(name, content)

    with pytest.raises(HearthPackageError, match="non-portable path"):
        import_hearth_package(unsafe, tmp_path / "unsafe-home")


def test_export_and_import_refuse_to_replace_existing_paths(tmp_path):
    home = _populated_home(tmp_path)
    package = tmp_path / "resident.wwhearth"
    package.write_bytes(b"do not replace")
    with pytest.raises(HearthPackageError, match="refusing to replace"):
        export_hearth_package(home, package)
    assert package.read_bytes() == b"do not replace"

    valid = tmp_path / "valid.wwhearth"
    export_hearth_package(home, valid)
    target = tmp_path / "existing-home"
    target.mkdir()
    with pytest.raises(HearthPackageError, match="refusing to replace"):
        import_hearth_package(valid, target)
