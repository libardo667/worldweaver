from __future__ import annotations

import asyncio

from src.identity.loader import LoopTuning, ResidentIdentity
from src.runtime.effectors import WorldEffector
from src.runtime.ledger import load_runtime_events
from src.runtime.pulse import Act
from src.runtime.workshop import Workshop


def _identity():
    return ResidentIdentity(
        name="marina",
        actor_id="ws",
        soul="",
        canonical_soul="",
        growth_soul="",
        vibe="",
        core="",
        voice_seed=[],
        tuning=LoopTuning(),
    )


def test_workshop_appends_and_reads_back(tmp_path):
    ws = Workshop(tmp_path / "workshop")
    r1 = ws.append(
        "Inspected the cornices on Steiner. Sag is worse than the report says.",
        title="Field note",
    )
    r2 = ws.append("Sourdough rises slower in the fog. Noted for the brick oven.")
    assert r1["written"] and r1["artifact"] == "journal.md"
    assert r2["written"]
    entries = ws.recent(5)
    assert len(entries) == 2
    assert entries[0]["title"] == "Field note"
    assert "cornices" in entries[0]["body"]
    assert ws.artifacts() == ["journal.md"]


def test_resident_markdown_headings_remain_inside_one_workshop_entry(tmp_path):
    ws = Workshop(tmp_path / "workshop")
    result = ws.append(
        "# Main thought\n\n## Workshop note — 2026-06-14\n\nThe nested heading belongs to this page.",
        title="Field note\ncontinued",
    )

    entries = ws.recent(5)
    summary = ws.summary()[0]

    assert len(entries) == 1
    assert entries[0]["ts"] == result["ts"]
    assert entries[0]["title"] == "Field note continued"
    assert "## Workshop note — 2026-06-14" in entries[0]["body"]
    assert summary["count"] == 1
    assert summary["last_ts"] == result["ts"]


def test_workshop_separate_artifacts(tmp_path):
    ws = Workshop(tmp_path / "workshop")
    ws.append("page one of the zine", artifact="zine")
    ws.append("a journal line", artifact="journal")
    assert set(ws.artifacts()) == {"zine.md", "journal.md"}
    assert "page one" in ws.recent(1, artifact="zine.md")[0]["body"]


def test_workshop_cannot_escape_its_directory(tmp_path):
    ws = Workshop(tmp_path / "marina" / "workshop")
    outside = tmp_path / "secret.md"
    # Path-traversal and absolute targets are sanitized to stay inside the workspace.
    for hostile in [
        "../../secret",
        "../../../etc/passwd",
        "/etc/passwd",
        "..\\..\\windows",
    ]:
        res = ws.append("should not escape", artifact=hostile)
        assert res["written"] is True  # it writes — but inside the workshop
    assert not outside.exists()
    # Everything landed under the workshop root, nowhere else.
    for p in (tmp_path / "marina" / "workshop").glob("*.md"):
        assert (tmp_path / "marina" / "workshop") in p.resolve().parents


def test_workshop_empty_body_is_noop(tmp_path):
    ws = Workshop(tmp_path / "workshop")
    assert ws.append("   ")["written"] is False
    assert ws.recent() == []


def test_effector_routes_write_to_workshop_not_mail(tmp_path):
    ws = Workshop(tmp_path / "workshop")

    class _W:
        def __init__(self):
            self.letters = []

        async def send_letter(self, **k):
            self.letters.append(k)
            return {"ok": True}

    world = _W()
    eff = WorldEffector(
        ww_client=world,
        session_id="s",
        identity=_identity(),
        memory_dir=tmp_path,
        workshop=ws,
    )

    res = asyncio.run(
        eff(
            Act(
                kind="write",
                body="Today the Painted Ladies leaned a half-inch more.",
                target="journal",
            )
        )
    )
    assert res["executed"] and res["workshop"] == "journal.md"
    assert world.letters == []  # went to the workshop, not the mail system
    assert "Painted Ladies" in ws.recent(1)[0]["body"]
    assert any(
        e.get("event_type") == "workshop_entry" for e in load_runtime_events(tmp_path)
    )

    # A write to an actual person still goes to mail.
    asyncio.run(eff(Act(kind="write", body="Come see the foundation.", target="Leo")))
    assert len(world.letters) == 1 and world.letters[0]["to_agent"] == "Leo"
