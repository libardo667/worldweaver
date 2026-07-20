from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _run(script: Path, private_key: Path, descriptor: Path | None = None):
    command = [sys.executable, str(script), "--private-key", str(private_key)]
    if descriptor is not None:
        command.extend(["--descriptor", str(descriptor)])
    return subprocess.run(command, capture_output=True, text=True)


def test_script_creates_verifies_and_repairs_public_descriptor(tmp_path):
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "hearth_transport_identity.py"
    )
    private_key = tmp_path / "hearth-host" / "identity" / "transport.key"
    descriptor = tmp_path / "hearth-host.json"

    created = _run(script, private_key, descriptor)
    assert created.returncode == 0, created.stderr
    created_payload = json.loads(created.stdout)
    assert created_payload["status"] == "created"
    assert private_key.stat().st_mode & 0o077 == 0

    existing = _run(script, private_key, descriptor)
    assert existing.returncode == 0, existing.stderr
    assert json.loads(existing.stdout)["status"] == "existing"

    descriptor.unlink()
    repaired = _run(script, private_key, descriptor)
    assert repaired.returncode == 0, repaired.stderr
    assert json.loads(repaired.stdout)["status"] == "repaired"
    assert json.loads(descriptor.read_text(encoding="utf-8")) == (
        created_payload["descriptor"]
    )


def test_script_refuses_orphaned_or_mismatched_public_descriptor(tmp_path):
    script = (
        Path(__file__).resolve().parents[2] / "scripts" / "hearth_transport_identity.py"
    )
    first_key = tmp_path / "first" / "transport.key"
    first_descriptor = tmp_path / "first.json"
    second_key = tmp_path / "second" / "transport.key"
    second_descriptor = tmp_path / "second.json"
    assert _run(script, first_key, first_descriptor).returncode == 0
    assert _run(script, second_key, second_descriptor).returncode == 0

    first_key.unlink()
    orphaned = _run(script, first_key, first_descriptor)
    assert orphaned.returncode == 1
    assert "private key is missing" in orphaned.stderr

    second_descriptor.write_bytes(first_descriptor.read_bytes())
    mismatched = _run(script, second_key, second_descriptor)
    assert mismatched.returncode == 1
    assert "does not match" in mismatched.stderr
