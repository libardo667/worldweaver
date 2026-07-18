from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from src.familiar import visual
from src.familiar.local_world import LocalWorld


def _deliver(home: Path, name: str, data: bytes, *, note: str = "") -> None:
    given = home / "workshop" / "given"
    given.mkdir(parents=True, exist_ok=True)
    destination = given / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(data)
    with (home / "given.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": datetime.now().astimezone().isoformat(),
                    "file": name,
                    "note": note,
                }
            )
            + "\n"
        )


def test_gifts_are_elective_records_not_ambient_scene_narration(tmp_path):
    home = tmp_path / "resident"
    world = LocalWorld(
        home_dir=home,
        keeper_name="",
        gifts_enabled=True,
        vision=True,
    )
    _deliver(
        home,
        "picture.png",
        visual._png_encode(1, 1, 3, b"\xff\x00\x00", 3),
        note="the red square",
    )

    scene = asyncio.run(world.get_scene("resident-hearth"))
    listing = asyncio.run(world.access_information(kind="inspect", source="gifts", query=""))
    opened = asyncio.run(world.access_information(kind="read", source="gifts", query="picture.png"))

    assert scene.present == []
    assert scene.recent_events_here == []
    assert "gifts" in [affordance.name for affordance in scene.affordances]
    assert listing["records"][0]["title"] == "picture.png"
    assert listing.get("images", []) == []
    assert opened["images"][0].startswith("data:image/png;base64,")
    assert "the red square" in opened["records"][0]["content"]


def test_gifts_source_does_not_exist_without_an_explicit_grant(tmp_path):
    home = tmp_path / "resident"
    world = LocalWorld(home_dir=home, keeper_name="")
    _deliver(home, "note.txt", b"hello")

    scene = asyncio.run(world.get_scene("resident-hearth"))
    result = asyncio.run(world.access_information(kind="read", source="gifts", query="note.txt"))

    assert "gifts" not in [affordance.name for affordance in scene.affordances]
    assert result["ok"] is False
    assert result["reason"] == "unknown_source"


def test_gifts_reopen_safe_nested_paths_from_a_carried_inbox(tmp_path):
    home = tmp_path / "resident"
    world = LocalWorld(home_dir=home, keeper_name="", gifts_enabled=True)
    _deliver(home, "inbox/72-salience.md", b"the carried page")

    listing = asyncio.run(world.access_information(kind="inspect", source="gifts", query=""))
    opened = asyncio.run(world.access_information(kind="read", source="gifts", query="given/inbox/72-salience.md"))
    reopened_by_unique_name = asyncio.run(world.access_information(kind="read", source="gifts", query="72-salience.md"))

    assert listing["records"][0]["title"] == "inbox/72-salience.md"
    assert opened["ok"] is True
    assert "the carried page" in opened["records"][0]["content"]
    assert reopened_by_unique_name["ok"] is True
    assert reopened_by_unique_name["records"][0]["title"] == "inbox/72-salience.md"


def test_gifts_reject_a_nested_path_that_could_escape_the_archive(tmp_path):
    home = tmp_path / "resident"
    world = LocalWorld(home_dir=home, keeper_name="", gifts_enabled=True)
    _deliver(home, "note.txt", b"safe")
    with (home / "given.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": datetime.now().astimezone().isoformat(), "file": "../outside.txt", "note": ""}) + "\n")

    listing = asyncio.run(world.access_information(kind="inspect", source="gifts", query=""))
    escaped = asyncio.run(world.access_information(kind="read", source="gifts", query="../outside.txt"))

    assert [record["title"] for record in listing["records"]] == ["note.txt"]
    assert escaped["ok"] is False
    assert escaped["reason"] == "gift_not_found"
    assert escaped["records"] == []


def test_give_command_stores_a_file_for_an_enabled_resident(tmp_path):
    home = tmp_path / "cinder"
    identity = home / "identity"
    identity.mkdir(parents=True)
    (identity / "SOUL.md").write_text("You are Cinder.\n", encoding="utf-8")
    (home / "hearth.json").write_text(json.dumps({"gifts": True}), encoding="utf-8")
    source = tmp_path / "letter.txt"
    source.write_text("hello from outside", encoding="utf-8")
    root = Path(__file__).resolve().parents[2]

    completed = subprocess.run(
        [
            sys.executable,
            str(root / "ww_agent" / "scripts" / "give.py"),
            str(home),
            str(source),
            "--note",
            "for later",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (home / "workshop" / "given" / "letter.txt").read_text(encoding="utf-8") == "hello from outside"
    notice = json.loads((home / "given.jsonl").read_text(encoding="utf-8").strip())
    assert notice["file"] == "letter.txt"
    assert notice["note"] == "for later"
