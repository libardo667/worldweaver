from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_familiar_command_runs_one_shared_resident_host_at_the_hearth(tmp_path):
    home = tmp_path / "cinder"
    identity = home / "identity"
    identity.mkdir(parents=True)
    (identity / "SOUL.md").write_text("You are Cinder.\n", encoding="utf-8")
    (home / "hearth.json").write_text(
        json.dumps({"place": "the quiet room"}),
        encoding="utf-8",
    )
    root = Path(__file__).resolve().parents[2]
    env = {
        key: value
        for key, value in os.environ.items()
        if key
        not in {
            "WW_INFERENCE_KEY",
            "WW_EMBEDDING_URL",
        }
    }

    completed = subprocess.run(
        [
            sys.executable,
            str(root / "ww_agent" / "scripts" / "familiar.py"),
            "--home",
            str(home),
            "--ticks",
            "1",
            "--pause",
            "0",
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "through the shared resident host" in completed.stdout
    assert "the quiet room" in completed.stdout
    assert (home / "state.json").exists()
    events = [json.loads(line) for line in (home / "memory" / "runtime_ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    attachment = next(event for event in events if event.get("event_type") == "world_attachment_changed")
    assert attachment["payload"]["to_world"] == "hearth"
    assert not (home / "session_id.txt").exists()
