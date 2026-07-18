from __future__ import annotations

import asyncio
import json
from datetime import datetime

from src.familiar.file_scope import FileScope
from src.familiar.local_world import LocalWorld
from src.familiar import visual
from src.runtime.information import InformationSourceRegistry
from src.runtime.prompt_context import PulseContext, render_affordance_catalog
from src.runtime.travel import TravelRequest
from src.runtime.perception import _reachable_destinations


def _tree(tmp_path):
    (tmp_path / "notes.md").write_text("hello, this is fine to read", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET_KEY=hunter2", encoding="utf-8")
    (tmp_path / "config.key").write_text("-----BEGIN KEY-----", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("build/\n*.log\n", encoding="utf-8")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "out.txt").write_text("artifact", encoding="utf-8")
    (tmp_path / "run.log").write_text("logs", encoding="utf-8")
    sub = tmp_path / "src"
    sub.mkdir()
    (sub / "main.py").write_text("print('hi')", encoding="utf-8")
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "token.txt").write_text("abc", encoding="utf-8")
    return FileScope(read_roots=[tmp_path])


def test_reads_normal_files(tmp_path):
    fs = _tree(tmp_path)
    assert fs.read("notes.md")["ok"] is True
    assert "fine to read" in fs.read("notes.md")["content"]
    assert fs.read("src/main.py")["ok"] is True


def test_visual_read_keeps_scope_and_secret_guards(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    (root / "picture.png").write_bytes(visual._png_encode(1, 1, 3, b"\xff\x00\x00", 3))
    (root / "notes.md").write_text("not visual", encoding="utf-8")
    (root / ".env").write_bytes(b"\x89PNG\r\n\x1a\nsecret")
    scope = FileScope(read_roots=[root])

    assert scope.read_media("picture.png")["kind"] == "image"
    assert scope.read_media("notes.md")["reason"] == "not_visual"
    assert scope.read_media(".env")["reason"] == "ignored"
    assert scope.read_media("/etc/passwd")["reason"] == "outside_scope"


def test_default_deny_hides_secrets_even_without_gitignore(tmp_path):
    fs = _tree(tmp_path)
    assert fs.read(".env") == {"ok": False, "reason": "ignored"} or fs.read(".env")["reason"] == "ignored"
    assert fs.read("config.key")["ok"] is False  # *.key
    assert fs.read("secrets/token.txt")["ok"] is False  # *secret* dir


def test_gitignore_is_respected(tmp_path):
    fs = _tree(tmp_path)
    assert fs.read("run.log")["ok"] is False  # *.log
    assert fs.read("build/out.txt")["ok"] is False  # build/ dir-only pattern hides contents


def test_cannot_escape_the_root(tmp_path):
    fs = _tree(tmp_path)
    assert fs.read("/etc/passwd")["reason"] == "outside_scope"
    assert fs.read("../../../../etc/passwd")["reason"] == "outside_scope"
    assert fs.read("src/../../../../etc/hosts")["reason"] == "outside_scope"


def test_tree_and_listdir_omit_hidden(tmp_path):
    fs = _tree(tmp_path)
    tree = fs.tree(max_depth=3, max_entries=100)
    assert "notes.md" in tree and "src/main.py" in tree
    assert not any(".env" in t or "build" in t or ".log" in t or "secrets" in t for t in tree)
    names = [e["name"] for e in fs.listdir()["entries"]]
    assert "notes.md" in names and ".env" not in names and "secrets" not in names


def test_multi_root_qualifies_paths_and_resolves_them(tmp_path):
    # two roots → entries are root-qualified ("alpha/notes.md") so the listing is legible
    # and each qualified path round-trips back through read(); a single root stays bare.
    a = tmp_path / "alpha"
    a.mkdir()
    b = tmp_path / "beta"
    b.mkdir()
    (a / "notes.md").write_text("from alpha", encoding="utf-8")
    (b / "notes.md").write_text("from beta", encoding="utf-8")
    fs = FileScope(read_roots=[a, b])
    tree = fs.tree(max_depth=1, max_entries=50)
    assert "alpha/notes.md" in tree and "beta/notes.md" in tree
    # the root name disambiguates two same-named files
    assert fs.read("alpha/notes.md")["content"] == "from alpha"
    assert fs.read("beta/notes.md")["content"] == "from beta"
    # read echoes the qualified path so the hint, the typed path, and the echo all agree
    assert fs.read("beta/notes.md")["path"] == "beta/notes.md"

    # A root name itself opens the root folder, rather than becoming a missing path.
    assert fs.listdir("beta")["path"] == "beta"


def test_single_root_stays_unqualified(tmp_path):
    # one root → no prefix, identical to pre-multi-root behavior
    (tmp_path / "notes.md").write_text("solo", encoding="utf-8")
    fs = FileScope(read_roots=[tmp_path])
    assert "notes.md" in fs.tree(max_depth=1, max_entries=10)
    assert fs.read("notes.md")["path"] == "notes.md"


def test_multi_root_still_refuses_escape_and_secrets(tmp_path):
    a = tmp_path / "alpha"
    a.mkdir()
    b = tmp_path / "beta"
    b.mkdir()
    (b / ".env").write_text("SECRET=x", encoding="utf-8")
    fs = FileScope(read_roots=[a, b])
    assert fs.read("beta/.env")["ok"] is False  # default-deny holds across roots
    assert fs.read("../../../etc/passwd")["reason"] == "outside_scope"


def test_local_world_exposes_files_as_typed_private_information(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    (root / "notes.md").write_text("a private page about blue herons", encoding="utf-8")
    home = tmp_path / "home"
    (home / "memory").mkdir(parents=True)
    (home / "memory" / "kept_memory.jsonl").write_text('{"note":"the red kettle belongs by the window"}\n', encoding="utf-8")
    world = LocalWorld(home_dir=home, file_scope=FileScope(read_roots=[root]))

    scene = asyncio.run(world.get_scene("familiar-1"))
    assert scene.recent_events_here == []
    assert [(item.name, item.source_id) for item in scene.affordances] == [
        ("recall", "source:recall"),
        ("measure", "source:measure"),
        ("files", "source:files"),
    ]
    files = next(item for item in scene.affordances if item.name == "files")
    assert files.provenance == "scoped-reading"
    assert isinstance(world.information_sources(), InformationSourceRegistry)

    result = asyncio.run(world.access_information(kind="read", source="files", query="notes.md"))
    assert result["ok"] is True
    assert "blue herons" in result["records"][0]["content"]
    assert result["provenance"] == "scoped-reading"
    assert result["records"][0]["provenance"] == "scoped-reading"
    assert result["selection_mode"] == "exact_path"

    recalled = asyncio.run(world.access_information(kind="inspect", source="recall", query="kettle"))
    assert recalled["provenance"] == "self-memory"
    assert "red kettle" in recalled["records"][0]["content"]

    catalog = render_affordance_catalog(
        PulseContext.from_perception(
            {"affordances": [vars(item) for item in scene.affordances]},
            mode="react",
        )
    )
    assert "authorized artifacts" in catalog
    assert "read or consulted it rather than already knowing it" in catalog
    assert "CALCULATE privately" in catalog
    assert "local computed results" in catalog
    assert "speak their results as your own knowing" not in catalog


def test_scoped_read_pages_large_files_and_names_the_next_page(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    content = "a" * 12_000 + "PAGE TWO" + "b" * 12_000 + "PAGE THREE"
    (root / "long.txt").write_text(content, encoding="utf-8")
    world = LocalWorld(
        home_dir=tmp_path / "home",
        file_scope=FileScope(read_roots=[root]),
    )

    first = asyncio.run(world.access_information(kind="read", source="files", query="long.txt"))
    second = asyncio.run(
        world.access_information(
            kind="read",
            source="files",
            query="long.txt page 2",
        )
    )

    assert "page 1 of 3" in first["records"][0]["title"]
    assert first["records"][0]["metadata"]["has_more"] is True
    assert "PAGE TWO" in second["records"][0]["content"]
    assert second["records"][0]["metadata"]["page"] == 2


def test_scoped_read_suggests_an_allowed_same_named_file(tmp_path):
    root = tmp_path / "shared"
    (root / "nested").mkdir(parents=True)
    (root / "nested" / "notes.md").write_text("found", encoding="utf-8")
    world = LocalWorld(
        home_dir=tmp_path / "home",
        file_scope=FileScope(read_roots=[root]),
    )

    result = asyncio.run(
        world.access_information(
            kind="read",
            source="files",
            query="wrong/notes.md",
        )
    )

    assert result["ok"] is False
    assert "nested/notes.md" in result["reason"]


def test_scoped_visual_read_returns_images_only_with_explicit_vision(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    (root / "picture.png").write_bytes(visual._png_encode(1, 1, 3, b"\xff\x00\x00", 3))

    sighted = LocalWorld(
        home_dir=tmp_path / "sighted",
        file_scope=FileScope(read_roots=[root]),
        vision=True,
    )
    text_only = LocalWorld(
        home_dir=tmp_path / "text-only",
        file_scope=FileScope(read_roots=[root]),
    )

    seen = asyncio.run(sighted.access_information(kind="read", source="files", query="picture.png"))
    unseen = asyncio.run(text_only.access_information(kind="read", source="files", query="picture.png"))

    assert seen["images"][0].startswith("data:image/png;base64,")
    assert unseen.get("images", []) == []
    assert "cannot see" in unseen["records"][0]["content"]


def test_local_world_keeps_resident_recall_without_a_file_grant(tmp_path):
    world = LocalWorld(home_dir=tmp_path / "home")

    scene = asyncio.run(world.get_scene("resident-hearth"))

    assert [(item.name, item.provenance) for item in scene.affordances] == [
        ("recall", "self-memory"),
        ("measure", "local-computation"),
    ]


def test_local_world_does_not_treat_read_syntax_as_physical_do(tmp_path):
    root = tmp_path / "shared"
    root.mkdir()
    (root / "notes.md").write_text("private", encoding="utf-8")
    world = LocalWorld(home_dir=tmp_path / "home", file_scope=FileScope(read_roots=[root]))

    result = asyncio.run(world.post_action("familiar-1", "read notes.md"))

    assert "private information reach" in result.narrative
    assert world.gestures == []


def test_unkept_hearth_is_private_without_inventing_a_keeper(tmp_path):
    world = LocalWorld(
        home_dir=tmp_path / "home",
        keeper_name="",
        familiar_name="Resident",
        city_names={"city"},
    )

    facts = world.situational_facts()
    scene = asyncio.run(world.get_scene("resident-hearth"))

    assert facts["solo"] is True
    assert facts["inner_private"] is True
    assert facts["private_making_space"] is True
    assert "keeper" not in facts
    assert "city" in facts["travel"]
    assert scene.present == []
    assert _reachable_destinations(scene.location, scene.location_graph) == ["city"]
    assert asyncio.run(world.get_place_names()) == {"the hearth", "city"}


def test_hearth_travel_request_is_consumed_once(tmp_path):
    world = LocalWorld(
        home_dir=tmp_path / "home",
        keeper_name="",
        city_names={"city"},
    )

    result = asyncio.run(world.post_map_move("resident-hearth", "travel to city"))

    assert result["travel_pending"] is True
    assert world.take_pending_travel() == TravelRequest("city", "city")
    assert world.take_pending_travel() is None

    action = asyncio.run(world.post_action("resident-hearth", "return to city"))
    assert action.travel_pending is True
    assert world.take_pending_travel() == TravelRequest("city", "city")


def test_keeper_whisper_rouses_once_without_replaying_on_world_build(tmp_path):
    home = tmp_path / "home"
    world = LocalWorld(
        home_dir=home,
        keeper_name="Levi",
        familiar_name="Resident",
    )
    assert world.take_force_ignite() is False

    with (home / "whispers.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(
            json.dumps(
                {
                    "ts": datetime.now().astimezone().isoformat(),
                    "text": "Are you there?",
                }
            )
            + "\n"
        )

    assert world.take_force_ignite() is True
    assert world.take_force_ignite() is False

    rebuilt = LocalWorld(
        home_dir=home,
        keeper_name="Levi",
        familiar_name="Resident",
    )
    assert rebuilt.take_force_ignite() is False
