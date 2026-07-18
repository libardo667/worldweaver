import subprocess
import sys
from pathlib import Path


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
    assert "name: ww_dev_federation" in compose_text
    assert "- ww_alderbank-backend" in compose_text
