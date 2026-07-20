from __future__ import annotations

import asyncio
from pathlib import Path
import stat

import pytest

import src.resident as resident_module
from src.identity.hearth_permissions import (
    HearthPermissionError,
    secure_hearth_permissions,
)
from src.resident import Resident


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.lstat().st_mode)


def test_secure_hearth_permissions_repairs_nested_files_without_following_links(tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("not part of the hearth", encoding="utf-8")
    outside.chmod(0o644)

    home = tmp_path / "resident"
    memory = home / "memory"
    memory.mkdir(parents=True, mode=0o755)
    ledger = memory / "runtime_ledger.jsonl"
    ledger.write_text("{}\n", encoding="utf-8")
    ledger.chmod(0o644)
    (home / "outside-link").symlink_to(outside)
    home.chmod(0o755)
    memory.chmod(0o755)

    report = secure_hearth_permissions(home)

    assert _mode(home) == 0o700
    assert _mode(memory) == 0o700
    assert _mode(ledger) == 0o600
    assert _mode(outside) == 0o644
    assert report.directories_changed == 2
    assert report.files_changed == 1
    assert report.symlinks_skipped == 1


def test_secure_hearth_permissions_rejects_a_linked_root(tmp_path):
    actual = tmp_path / "actual"
    actual.mkdir()
    linked = tmp_path / "linked"
    linked.symlink_to(actual, target_is_directory=True)

    with pytest.raises(HearthPermissionError, match="must not be a symbolic link"):
        secure_hearth_permissions(linked)


def test_resident_start_repairs_existing_hearth_before_attachment(tmp_path, monkeypatch):
    home = tmp_path / "resident"
    identity = home / "identity"
    identity.mkdir(parents=True)
    private_file = identity / "SOUL.md"
    private_file.write_text("private", encoding="utf-8")
    home.chmod(0o755)
    identity.chmod(0o755)
    private_file.chmod(0o644)

    class Lease:
        def release(self):
            return None

    monkeypatch.setattr(resident_module, "acquire_hearth_runtime", lambda _home: Lease())
    resident = Resident(home, ww_client=object(), llm=object())

    async def attach(_world_id, *, default_attachment="city"):
        assert default_attachment == "city"

    monkeypatch.setattr(resident, "_start_attached", attach)

    asyncio.run(resident.start("test-world"))
    created_during_run = home / "memory" / "new-private-record.jsonl"
    created_during_run.parent.mkdir()
    created_during_run.write_text("{}\n", encoding="utf-8")
    created_during_run.chmod(0o644)
    resident._release_runtime_lease()

    assert _mode(home) == 0o700
    assert _mode(identity) == 0o700
    assert _mode(private_file) == 0o600
    assert _mode(created_during_run.parent) == 0o700
    assert _mode(created_during_run) == 0o600
