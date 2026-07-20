from __future__ import annotations

import json

from scripts.migrate_shard_identity import migrate_shard_identity


def test_migration_is_private_and_idempotent(tmp_path) -> None:
    shard = tmp_path / "river-node"
    shard.mkdir()
    (shard / ".env").write_text(
        "SHARD_ID=river-node-1\nCITY_ID=portland\nSHARD_TYPE=city\nFEDERATION_TOKEN=legacy-secret\n",
        encoding="utf-8",
    )
    (shard / "docker-compose.yml").write_text(
        "services:\n"
        "  backend:\n"
        "    image: worldweaver:test\n"
        "    volumes:\n"
        "      - ./data:/app/data\n",
        encoding="utf-8",
    )

    first = migrate_shard_identity(shard)
    original_key = (shard / "identity" / "node.key").read_text(encoding="utf-8")
    second = migrate_shard_identity(shard, drop_legacy_token=True)

    assert first == second
    assert (shard / "identity" / "node.key").read_text(encoding="utf-8") == original_key
    assert (shard / "identity" / "node.key").stat().st_mode & 0o077 == 0
    assert (shard / ".env").stat().st_mode & 0o077 == 0
    assert "WW_NODE_PRIVATE_KEY_PATH=identity/node.key" in (shard / ".env").read_text(
        encoding="utf-8"
    )
    assert "FEDERATION_TOKEN=\n" in (shard / ".env").read_text(encoding="utf-8")
    assert "legacy-secret" not in (shard / ".env").read_text(encoding="utf-8")
    assert (shard / "docker-compose.yml").read_text(encoding="utf-8").count(
        "./identity:/app/identity:ro"
    ) == 1
    assert (shard / ".gitignore").read_text(encoding="utf-8").count(
        "identity/node.key"
    ) == 1
    descriptor = json.loads((shard / "node.json").read_text(encoding="utf-8"))
    assert descriptor["node_id"] == "river-node-1"
    assert descriptor["public_key"] == first["public_key"]


def test_world_folder_uses_its_directory_name_when_legacy_env_has_no_id(
    tmp_path,
) -> None:
    shard = tmp_path / "ww_world"
    shard.mkdir()
    (shard / ".env").write_text("SHARD_TYPE=world\n", encoding="utf-8")
    (shard / "docker-compose.yml").write_text(
        "services:\n  backend:\n    volumes:\n      - ./data:/app/data\n",
        encoding="utf-8",
    )

    descriptor = migrate_shard_identity(shard)

    assert descriptor["node_id"] == "ww_world"
