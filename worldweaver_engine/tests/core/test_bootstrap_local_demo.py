import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "bootstrap_local_demo.py"


def _scaffold(tmp_path: Path) -> Path:
    root = tmp_path / "worldweaver"
    for shard in ("ww_world", "ww_alderbank"):
        shard_dir = root / "shards" / shard
        shard_dir.mkdir(parents=True)
        (shard_dir / "docker-compose.yml").write_text(
            "services: {}\n", encoding="utf-8"
        )
    city_pack = root / "worldweaver_engine" / "data" / "cities" / "alderbank"
    city_pack.mkdir(parents=True)
    (city_pack / "manifest.json").write_text("{}\n", encoding="utf-8")
    (city_pack / "neighborhoods.json").write_text("[]\n", encoding="utf-8")
    rulesets = root / "worldweaver_engine" / "data" / "rulesets"
    rulesets.mkdir(parents=True)
    (rulesets / "private_constructive_game.v1.example.json").write_text(
        "{}\n", encoding="utf-8"
    )
    return root


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--workspace-root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _env(path: Path) -> dict[str, str]:
    return dict(
        line.split("=", 1)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )


def test_bootstrap_creates_private_local_demo_state(tmp_path: Path) -> None:
    root = _scaffold(tmp_path)

    result = _run(root)

    assert result.returncode == 0, result.stderr
    world = root / "shards" / "ww_world"
    city = root / "shards" / "ww_alderbank"
    world_env = _env(world / ".env")
    city_env = _env(city / ".env")
    assert world_env["WW_FEDERATION_ADMISSION_MODE"] == "open"
    assert city_env["WW_RUNTIME_FEDERATION_URL"] == "http://ww_world-backend:8000"
    assert world_env["FEDERATION_TOKEN"] == city_env["FEDERATION_TOKEN"]
    assert world_env["WW_JWT_SECRET"] != city_env["WW_JWT_SECRET"]
    assert (world / ".env").stat().st_mode & 0o077 == 0
    assert (city / ".env").stat().st_mode & 0o077 == 0
    assert (world / "identity" / "node.key").stat().st_mode & 0o077 == 0
    assert (city / "identity" / "node.key").stat().st_mode & 0o077 == 0
    assert (world / "node.json").is_file()
    assert (city / "node.json").is_file()
    assert (city / "hearth-host.json").is_file()
    assert (city / "data" / "cities" / "alderbank" / "manifest.json").is_file()
    assert (
        city / "data" / "rulesets" / "private_constructive_game.v1.example.json"
    ).is_file()


def test_bootstrap_is_idempotent_after_success(tmp_path: Path) -> None:
    root = _scaffold(tmp_path)
    first = _run(root)
    env_path = root / "shards" / "ww_alderbank" / ".env"
    original = env_path.read_text(encoding="utf-8")

    second = _run(root)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "already initialized" in second.stdout
    assert env_path.read_text(encoding="utf-8") == original


def test_bootstrap_refuses_unmarked_existing_state(tmp_path: Path) -> None:
    root = _scaffold(tmp_path)
    env_path = root / "shards" / "ww_world" / ".env"
    env_path.write_text("DO_NOT_REPLACE=yes\n", encoding="utf-8")

    result = _run(root)

    assert result.returncode != 0
    assert "Existing local shard state was found" in result.stderr
    assert env_path.read_text(encoding="utf-8") == "DO_NOT_REPLACE=yes\n"
    assert not (root / "shards" / "ww_alderbank" / ".env").exists()
