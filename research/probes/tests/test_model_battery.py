from __future__ import annotations

import sys
from pathlib import Path

PROBES = Path(__file__).resolve().parents[1]
if str(PROBES) not in sys.path:
    sys.path.insert(0, str(PROBES))

from model_battery import classify_payload  # noqa: E402


def test_classification_accepts_a_quiet_valid_pulse():
    result = classify_payload(
        {
            "felt_sense": "quiet orientation",
            "reach": None,
            "act": None,
            "expectations": [],
            "drive_nudges": [],
            "self_delta": {},
            "trace_verdicts": [],
        }
    )

    assert result["valid_pulse"] is True
    assert result["reach_act_conflict"] is False


def test_classification_exposes_reach_and_act_conflict():
    result = classify_payload(
        {
            "felt_sense": "two impulses",
            "reach": {"kind": "inspect", "source": "surroundings", "query": "garden"},
            "act": {"kind": "move", "body": "Walk toward the garden."},
            "expectations": [],
            "drive_nudges": [],
            "self_delta": {},
            "trace_verdicts": [],
        }
    )

    assert result["valid_pulse"] is False
    assert result["reach_act_conflict"] is True
