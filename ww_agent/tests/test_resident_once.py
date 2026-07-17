from __future__ import annotations

from scripts.resident_once import _did_execute, _effective_model, inspect_resident_home
from src.identity.hearth_activation import (
    acquire_hearth_runtime,
    initialize_hearth_activation,
)
from src.identity.hearth_manifest import initialize_hearth_manifest


def _home(tmp_path, *, activate: bool):
    home = tmp_path / "only_resident"
    (home / "identity").mkdir(parents=True)
    (home / "identity" / "resident_id.txt").write_text("actor-only\n", encoding="utf-8")
    (home / "identity" / "SOUL.md").write_text(
        "# Synthetic resident\n", encoding="utf-8"
    )
    initialize_hearth_manifest(home)
    if activate:
        initialize_hearth_activation(home)
    return home


def test_home_preflight_requires_explicit_active_generation(tmp_path):
    home = _home(tmp_path, activate=False)

    checks, report = inspect_resident_home(home)

    by_name = {check["name"]: check for check in checks}
    assert by_name["resident_home"]["status"] == "pass"
    assert by_name["identity"]["status"] == "pass"
    assert by_name["portable_inventory"]["status"] == "pass"
    assert by_name["hearth_activation"] == {
        "name": "hearth_activation",
        "status": "fail",
        "detail": "dormant",
    }
    assert report["runtime_lock"]["status"] == "available"


def test_home_preflight_refuses_a_busy_resident(tmp_path):
    home = _home(tmp_path, activate=True)
    lease = acquire_hearth_runtime(home)
    try:
        checks, report = inspect_resident_home(home)
    finally:
        lease.release()

    by_name = {check["name"]: check for check in checks}
    assert by_name["hearth_activation"]["status"] == "pass"
    assert by_name["runtime_lock"]["status"] == "fail"
    assert report["runtime_lock"]["status"] == "busy"


def test_effective_model_prefers_resident_tuning(tmp_path):
    home = _home(tmp_path, activate=False)
    (home / "identity" / "tuning.json").write_text(
        '{"fast":{"model":"resident/model"}}\n', encoding="utf-8"
    )

    assert _effective_model(home, "shard/default") == "resident/model"


def test_tick_receipt_reads_effector_execution_flag():
    assert _did_execute({"executed": True}) is True
    assert _did_execute({"executed": False, "reason": "exception"}) is False
