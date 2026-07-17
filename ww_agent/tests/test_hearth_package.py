from __future__ import annotations

import json

from src.identity.hearth_package import classify_hearth_path, inventory_hearth
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
