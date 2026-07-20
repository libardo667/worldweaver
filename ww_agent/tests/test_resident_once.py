from __future__ import annotations

import argparse
import json

import pytest

from scripts.resident_once import (
    _did_execute,
    _effective_model,
    _inactive_tuning_fields,
    _parse_duration,
    _record_tick,
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


def test_preflight_names_loaded_but_inactive_loop_controls(tmp_path):
    home = _home(tmp_path, activate=False)
    (home / "identity" / "tuning.json").write_text(
        json.dumps(
            {
                "fast": {"model": "resident/model", "cooldown_seconds": 45},
                "slow": {"refractory_seconds": 90},
                "wander": {"enabled": True, "seconds": 420},
                "anchor_gating": True,
            }
        ),
        encoding="utf-8",
    )

    assert _inactive_tuning_fields(home) == [
        "fast.cooldown_seconds",
        "slow.refractory_seconds",
        "wander",
    ]


def test_tick_receipt_reads_effector_execution_flag():
    assert _did_execute({"executed": True}) is True
    assert _did_execute({"executed": False, "reason": "exception"}) is False


def test_tick_receipt_counts_attachment_mode_and_action_kind():
    from src.familiar.local_world import LocalWorld

    stats = {
        "ticks": 0,
        "ignitions": 0,
        "settling_pulses": 0,
        "fervor_pulses": 0,
        "venture_pulses": 0,
        "pulses_routed": 0,
        "information_requests": 0,
        "information_reads": 0,
        "duplicate_reads_avoided": 0,
        "read_budget_exhaustions": 0,
        "pulse_model_calls": 0,
        "pulse_elapsed_ms": 0.0,
        "acts_executed": 0,
        "resting_ticks": 0,
        "ticks_by_attachment": {},
        "actions_by_attachment": {},
        "action_kinds": {},
        "venture_gate_reasons": {},
    }
    world = object.__new__(LocalWorld)

    receipt = _record_tick(
        stats,
        world,
        {
            "ignited": False,
            "settled": True,
            "fervor": False,
            "venture": False,
            "pulse_routed": {"pulse_id": "pulse-test"},
            "information_accessed": [{"source": "recall"}],
            "pulse_metrics": {
                "information_requests": 2,
                "information_reads_served": 1,
                "duplicate_reads_avoided": 1,
                "read_budget_exhausted": True,
                "model_calls": 2,
                "elapsed_ms": 12.5,
            },
            "act_executed": {"executed": True, "kind": "write"},
            "resting": False,
            "venture_gate": {
                "enabled": True,
                "evaluated": True,
                "reason": "opened",
            },
        },
        1,
    )

    assert receipt == {
        "event": "resident_tick",
        "tick": 1,
        "attachment": "hearth",
        "mode": "settling",
        "pulse_routed": True,
        "information_requests": 2,
        "information_reads": 1,
        "duplicate_reads_avoided": 1,
        "read_budget_exhausted": True,
        "pulse_model_calls": 2,
        "pulse_elapsed_ms": 12.5,
        "act_executed": True,
        "act_kind": "write",
        "venture_gate": {
            "enabled": True,
            "evaluated": True,
            "reason": "opened",
        },
    }
    assert stats["ticks_by_attachment"] == {"hearth": 1}
    assert stats["actions_by_attachment"] == {"hearth": 1}
    assert stats["action_kinds"] == {"write": 1}
    assert stats["venture_gate_reasons"] == {"opened": 1}
    assert stats["information_requests"] == 2
    assert stats["duplicate_reads_avoided"] == 1
    assert stats["read_budget_exhaustions"] == 1


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
