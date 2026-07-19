import subprocess
import sys
import json
from pathlib import Path


def _read_env(path: Path) -> dict[str, str]:
    return dict(line.split("=", 1) for line in path.read_text(encoding="utf-8").splitlines() if line and not line.startswith("#") and "=" in line)


def test_new_shard_keeps_node_identity_separate_from_city_pack(tmp_path: Path) -> None:
    city_pack = tmp_path / "pack"
    city_pack.mkdir()
    (city_pack / "neighborhoods.json").write_text("[]", encoding="utf-8")

    script = Path(__file__).resolve().parents[2] / "scripts" / "new_shard.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "portland",
            "--base-dir",
            str(tmp_path),
            "--city-pack-dir",
            str(city_pack),
            "--shard-id",
            "rose-city-coop-1",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    env_text = (tmp_path / "ww_pdx" / ".env").read_text(encoding="utf-8")
    assert "CITY_ID=portland\n" in env_text
    assert "SHARD_ID=rose-city-coop-1\n" in env_text
    assert "COMPOSE_PROJECT_NAME=rose-city-coop-1\n" in env_text


def test_new_world_directory_is_closed_and_has_folder_local_trust_commands(tmp_path: Path) -> None:
    script = Path(__file__).resolve().parents[2] / "scripts" / "new_shard.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "world",
            "--type",
            "world",
            "--base-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    shard = tmp_path / "ww_world"
    generated_env = _read_env(shard / ".env")
    assert generated_env["SHARD_TYPE"] == "world"
    assert generated_env["WW_FEDERATION_ADMISSION_MODE"] == "closed"
    checked = subprocess.run(
        [sys.executable, str(shard / "ww.py"), "check", "--offline"],
        cwd=shard,
        capture_output=True,
        text=True,
    )
    node_help = subprocess.run(
        [sys.executable, str(shard / "ww.py"), "node", "--help"],
        cwd=shard,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stderr
    assert node_help.returncode == 0, node_help.stderr
    assert "admit" in node_help.stdout
    assert "revoke" in node_help.stdout
    assert "recover" in node_help.stdout


def test_new_shards_receive_separate_secure_local_secrets(tmp_path: Path) -> None:
    city_pack = tmp_path / "pack"
    city_pack.mkdir()
    (city_pack / "neighborhoods.json").write_text("[]", encoding="utf-8")
    script = Path(__file__).resolve().parents[2] / "scripts" / "new_shard.py"

    generated: list[dict[str, str]] = []
    for directory_name, shard_id in (("first", "river-coop-1"), ("second", "river-coop-2")):
        base_dir = tmp_path / directory_name
        subprocess.run(
            [
                sys.executable,
                str(script),
                "portland",
                "--base-dir",
                str(base_dir),
                "--city-pack-dir",
                str(city_pack),
                "--shard-id",
                shard_id,
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        env_path = base_dir / "ww_pdx" / ".env"
        generated.append(_read_env(env_path))
        assert env_path.stat().st_mode & 0o077 == 0
        assert (base_dir / "ww_pdx" / "identity" / "node.key").stat().st_mode & 0o077 == 0
        descriptor = json.loads((base_dir / "ww_pdx" / "node.json").read_text(encoding="utf-8"))
        assert descriptor["node_id"] == shard_id
        assert descriptor["city_id"] == "portland"

    first, second = generated
    assert first["COMPOSE_PROJECT_NAME"] == "river-coop-1"
    assert second["COMPOSE_PROJECT_NAME"] == "river-coop-2"
    assert len(first["WW_JWT_SECRET"]) >= 48
    assert len(first["WW_DATA_ENCRYPTION_KEY"]) == 44
    assert len(first["WW_DB_PASSWORD"]) >= 32
    assert first["WW_JWT_SECRET"] != second["WW_JWT_SECRET"]
    assert first["WW_DATA_ENCRYPTION_KEY"] != second["WW_DATA_ENCRYPTION_KEY"]
    assert first["WW_DB_PASSWORD"] != second["WW_DB_PASSWORD"]
    assert first["WW_NODE_PRIVATE_KEY_PATH"] == "identity/node.key"
    assert "CHANGE_ME" not in first["WW_JWT_SECRET"]


def test_new_game_shard_copies_versioned_experience_and_uses_readable_name(tmp_path: Path) -> None:
    city_pack = tmp_path / "pack"
    city_pack.mkdir()
    (city_pack / "neighborhoods.json").write_text("[]", encoding="utf-8")
    experience = tmp_path / "alderbank.game.json"
    experience.write_text(
        '{"schema":"worldweaver.shard-experience","schema_version":1}',
        encoding="utf-8",
    )

    script = Path(__file__).resolve().parents[2] / "scripts" / "new_shard.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "alderbank",
            "--base-dir",
            str(tmp_path),
            "--city-pack-dir",
            str(city_pack),
            "--experience",
            str(experience),
            "--federation",
            "http://localhost:9000",
            "--runtime-federation",
            "http://ww_world-backend:8000",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    shard = tmp_path / "ww_alderbank"
    env_text = (shard / ".env").read_text(encoding="utf-8")
    assert "CITY_ID=alderbank\n" in env_text
    assert "SHARD_ID=ww_alderbank\n" in env_text
    assert "WW_SHARD_EXPERIENCE_PATH=/app/data/rulesets/alderbank.game.json\n" in env_text
    assert "FEDERATION_URL=http://localhost:9000\n" in env_text
    assert "WW_RUNTIME_FEDERATION_URL=http://ww_world-backend:8000\n" in env_text
    assert (shard / "data" / "rulesets" / "alderbank.game.json").read_text(encoding="utf-8") == experience.read_text(encoding="utf-8")
    compose_text = (shard / "docker-compose.yml").read_text(encoding="utf-8")
    assert "../../worldweaver_engine" not in compose_text
    assert "../../ww_agent" not in compose_text
    assert "ww_dev_federation" not in compose_text
    assert "image: ${WW_ENGINE_IMAGE}" in compose_text
    assert "image: ${WW_AGENT_IMAGE}" in compose_text

    generated_env = _read_env(shard / ".env")
    assert generated_env["WW_ENGINE_IMAGE"].startswith("ghcr.io/libardo667/worldweaver-engine:sha-")
    assert generated_env["WW_AGENT_IMAGE"].startswith("ghcr.io/libardo667/worldweaver-agent:sha-")
    assert (shard / "ww.py").is_file()
    checked = subprocess.run(
        [sys.executable, str(shard / "ww.py"), "check", "--offline"],
        cwd=shard,
        capture_output=True,
        text=True,
    )
    assert checked.returncode == 0, checked.stderr
    assert "Node folder check passed" in checked.stdout
