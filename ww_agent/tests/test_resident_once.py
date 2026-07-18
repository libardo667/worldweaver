from __future__ import annotations

import argparse

import pytest

from scripts.resident_once import (
    _did_execute,
    _effective_model,
    _parse_duration,
    inspect_resident_home,
    main,
)
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


def test_duration_parser_accepts_operator_units():
    assert _parse_duration("30s") == 30
    assert _parse_duration("15m") == 900
    assert _parse_duration("1h") == 3600


def test_duration_parser_rejects_nonpositive_and_overlong_runs():
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_duration("0m")
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_duration("3h")


def test_duration_mode_refuses_a_compressed_pause():
    with pytest.raises(SystemExit) as exc:
        main(
            [
                "--home",
                "/tmp/resident",
                "--server-url",
                "http://localhost:8000",
                "--duration",
                "15m",
                "--pause",
                "0.5",
            ]
        )

    assert exc.value.code == 2
