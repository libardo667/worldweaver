from __future__ import annotations

import json

from scripts.import_stable_hearth import import_stable_hearth, inspect_stable_hearth
from src.identity.hearth_activation import inspect_hearth_activation
from src.identity.hearth_package import inventory_hearth


def _legacy_home(tmp_path):
    home = tmp_path / "stable" / "familiar" / "maker"
    (home / "identity").mkdir(parents=True)
    (home / "memory").mkdir()
    (home / "workshop").mkdir()
    (home / "identity" / "SOUL.canonical.md").write_text(
        "# Maker\n\nMakes carefully.\n", encoding="utf-8"
    )
    (home / "identity" / "resident_id.txt").write_text(
        "actor-maker\n", encoding="utf-8"
    )
    (home / "memory" / "runtime_ledger.jsonl").write_text(
        json.dumps(
            {
                "event_id": "old-event",
                "event_type": "felt_sense_logged",
                "ts": "2026-06-01T00:00:00+00:00",
                "payload": {"felt_sense": "still here"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (home / "memory" / "runtime_projection.json").write_text("{}\n", encoding="utf-8")
    (home / "voice.jsonl").write_text(
        '{"kind":"speak","text":"hello"}\n', encoding="utf-8"
    )
    (home / "workshop" / "notebook.md").write_text("notes\n", encoding="utf-8")
    (home / "daemon.log").write_text("host log\n", encoding="utf-8")
    (home / "state.json").write_text("{}\n", encoding="utf-8")
    (home / "familiar.json").write_text(
        json.dumps(
            {
                "model": "test/model",
                "anchor_gating": True,
                "read_roots": ["/old/private/path"],
                "tools": ["old-tool"],
                "cities": {"old": "http://old.invalid"},
            }
        ),
        encoding="utf-8",
    )
    return home


def test_stable_import_preserves_resident_state_but_not_old_host_runtime(tmp_path):
    source = _legacy_home(tmp_path)
    target = tmp_path / "worldweaver" / "residents" / "maker"
    target.parent.mkdir(parents=True)
    granted = tmp_path / "worldweaver"
    report = import_stable_hearth(
        source,
        target,
        place="the workbench",
        read_roots=(granted,),
    )

    assert report["status"] == "imported_dormant"
    assert (target / "identity" / "resident_id.txt").read_text() == "actor-maker\n"
    assert (target / "identity" / "SOUL.md").read_text().startswith("# Maker")
    assert (target / "memory" / "runtime_ledger.jsonl").read_text().count("\n") == 2
    assert (target / "voice.jsonl").is_file()
    assert (target / "workshop" / "notebook.md").is_file()
    assert not (target / "daemon.log").exists()
    assert not (target / "state.json").exists()
    assert not (target / "familiar.json").exists()
    assert (target / "memory" / "runtime_projection.json").read_text() != "{}\n"
    hearth = json.loads((target / "hearth.json").read_text())
    assert hearth == {"place": "the workbench", "read_roots": [str(granted.resolve())]}
    tuning = json.loads((target / "identity" / "tuning.json").read_text())
    assert tuning["anchor_gating"] is True
    assert tuning["slow"]["model"] == "test/model"
    assert inspect_hearth_activation(target)["status"] == "dormant"
    assert inventory_hearth(target).blocked is False


def test_stable_inspection_is_read_only(tmp_path):
    source = _legacy_home(tmp_path)
    before = sorted(path.relative_to(source) for path in source.rglob("*"))

    report = inspect_stable_hearth(source)

    assert report["status"] == "ready"
    assert report["legacy_model"] == "test/model"
    assert sorted(path.relative_to(source) for path in source.rglob("*")) == before


def test_stable_import_keeps_a_carried_gift_archive_readable(tmp_path):
    source = _legacy_home(tmp_path)
    carried = source / "workshop" / "given" / "inbox" / "72-salience.md"
    carried.parent.mkdir(parents=True)
    carried.write_text("a carried page\n", encoding="utf-8")
    (source / "given.jsonl").write_text(
        json.dumps(
            {
                "ts": "2026-06-15T00:00:00+00:00",
                "file": "inbox/72-salience.md",
                "note": "",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    target = tmp_path / "worldweaver" / "residents" / "maker"
    target.parent.mkdir(parents=True)

    import_stable_hearth(source, target)

    hearth = json.loads((target / "hearth.json").read_text(encoding="utf-8"))
    assert hearth["gifts"] is True
    assert (target / "workshop" / "given" / "inbox" / "72-salience.md").read_text(
        encoding="utf-8"
    ) == "a carried page\n"
