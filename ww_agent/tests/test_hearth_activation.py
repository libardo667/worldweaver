from __future__ import annotations

import json

import pytest

from src.identity.hearth_activation import (
    HEARTH_ACTIVATION_FILENAME,
    HearthActivationError,
    HearthRuntimeLease,
    acquire_hearth_runtime,
    activate_imported_hearth,
    initialize_hearth_activation,
    inspect_hearth_activation,
    inspect_runtime_lock,
    load_hearth_activation,
)
from src.identity.hearth_manifest import (
    initialize_hearth_manifest,
    load_hearth_manifest,
)
from src.identity.hearth_package import (
    HearthPackageError,
    export_hearth_package,
    import_hearth_package,
    inventory_hearth,
)


def _home(tmp_path, name: str = "resident"):
    home = tmp_path / name
    (home / "identity").mkdir(parents=True)
    (home / "identity" / "resident_id.txt").write_text("actor-123\n", encoding="utf-8")
    initialize_hearth_manifest(home)
    return home


def test_manifested_home_is_dormant_until_explicit_first_activation(tmp_path):
    home = _home(tmp_path)

    assert inspect_hearth_activation(home)["status"] == "dormant"
    with pytest.raises(HearthActivationError, match="missing"):
        acquire_hearth_runtime(home)

    activation = initialize_hearth_activation(home)
    assert activation.state == "active"
    assert activation.runtime_generation == 1
    assert inspect_hearth_activation(home)["status"] == "active"


def test_runtime_lease_refuses_two_processes_for_the_same_home(tmp_path):
    home = _home(tmp_path)
    initialize_hearth_activation(home)

    first = acquire_hearth_runtime(home)
    try:
        assert inspect_runtime_lock(home)["status"] == "busy"
        with pytest.raises(HearthActivationError, match="already running"):
            acquire_hearth_runtime(home)
    finally:
        first.release()

    assert inspect_runtime_lock(home)["status"] == "available"
    second = acquire_hearth_runtime(home)
    second.release()


def test_import_is_dormant_then_transfer_retires_source_and_advances_target(tmp_path):
    source = _home(tmp_path, "source")
    initialize_hearth_activation(source)
    (source / "memory").mkdir()
    (source / "memory" / "runtime_ledger.jsonl").write_text(
        '{"event":"one"}\n', encoding="utf-8"
    )
    package = tmp_path / "resident.wwhearth"
    export_hearth_package(source, package)
    target = tmp_path / "target"
    import_hearth_package(package, target)

    assert inspect_hearth_activation(target)["status"] == "dormant"
    target_activation = activate_imported_hearth(source, target)

    assert target_activation.state == "active"
    assert target_activation.runtime_generation == 2
    assert load_hearth_manifest(source).runtime_generation == 1
    assert load_hearth_activation(source).state == "retired"
    assert load_hearth_manifest(target).runtime_generation == 2
    assert load_hearth_activation(target).state == "active"
    with pytest.raises(HearthActivationError, match="retired"):
        acquire_hearth_runtime(source)
    lease = acquire_hearth_runtime(target)
    lease.release()

    # A completed transfer can be checked or resumed without incrementing again.
    repeated = activate_imported_hearth(source, target)
    assert repeated == target_activation
    assert load_hearth_manifest(target).runtime_generation == 2


def test_activation_is_host_local_and_never_enters_the_package(tmp_path):
    source = _home(tmp_path, "source")
    initialize_hearth_activation(source)
    inventory = inventory_hearth(source)
    by_path = {item.path: item for item in inventory.items}
    assert by_path[HEARTH_ACTIVATION_FILENAME].disposition == "host_specific"

    package = tmp_path / "resident.wwhearth"
    report = export_hearth_package(source, package)
    assert HEARTH_ACTIVATION_FILENAME not in {
        record["path"] for record in report["files"]
    }


def test_transfer_refuses_a_running_source_without_changing_either_copy(tmp_path):
    source = _home(tmp_path, "source")
    initialize_hearth_activation(source)
    package = tmp_path / "resident.wwhearth"
    export_hearth_package(source, package)
    target = tmp_path / "target"
    import_hearth_package(package, target)
    source_manifest_before = load_hearth_manifest(source)
    target_manifest_before = load_hearth_manifest(target)

    running = HearthRuntimeLease(source).acquire()
    try:
        with pytest.raises(HearthActivationError, match="already running"):
            activate_imported_hearth(source, target)
    finally:
        running.release()

    assert load_hearth_manifest(source) == source_manifest_before
    assert load_hearth_manifest(target) == target_manifest_before
    assert not (target / HEARTH_ACTIVATION_FILENAME).exists()


def test_export_refuses_a_running_source(tmp_path):
    source = _home(tmp_path, "source")
    initialize_hearth_activation(source)
    running = acquire_hearth_runtime(source)
    try:
        with pytest.raises(HearthPackageError, match="already running"):
            export_hearth_package(source, tmp_path / "resident.wwhearth")
    finally:
        running.release()


def test_mismatched_activation_generation_fails_closed(tmp_path):
    home = _home(tmp_path)
    initialize_hearth_activation(home)
    path = home / HEARTH_ACTIVATION_FILENAME
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["runtime_generation"] = 99
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(HearthActivationError, match="does not match"):
        acquire_hearth_runtime(home)
