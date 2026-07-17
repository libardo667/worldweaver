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
