"""Integration checks for the narrative evaluation harness script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tests.integration_harness_helpers import NARRATIVE_EVAL_METRIC_KEYS, assert_metric_keys_present


ROOT = Path(__file__).resolve().parents[2]


def test_narrative_eval_smoke_runs_and_writes_artifacts(tmp_path: Path):
    out_dir = tmp_path / "narrative_eval"
    history_file = tmp_path / "history.jsonl"
    scenario_file = ROOT / "tests" / "integration" / "narrative_eval_scenarios.json"
    baseline_file = ROOT / "tests" / "integration" / "narrative_eval_baseline.json"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/eval_narrative.py",
            "--smoke",
            "--enforce",
            "--scenario-file",
            str(scenario_file),
            "--baseline-file",
            str(baseline_file),
            "--out-dir",
            str(out_dir),
            "--history-file",
            str(history_file),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    latest = out_dir / "latest.json"
    assert latest.exists()
    payload = json.loads(latest.read_text(encoding="utf-8"))
    metrics = payload.get("metrics", {})

    assert_metric_keys_present(metrics, NARRATIVE_EVAL_METRIC_KEYS)
    assert isinstance(payload.get("success_criteria_map"), dict)
    assert history_file.exists()
