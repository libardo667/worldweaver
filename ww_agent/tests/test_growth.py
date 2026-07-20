from __future__ import annotations

import asyncio
import json
from pathlib import Path

import src.runtime.cognitive_core as cognitive_core_module
from src.familiar.local_world import LocalWorld
from src.identity.growth import (
    adopt_growth_candidate,
    read_growth_candidate,
    repair_growth_adoptions,
)
from src.identity.loader import IdentityLoader
from src.runtime.effectors import WorldEffector
from src.runtime.information import InformationAccess
from src.runtime.ledger import load_runtime_events
from src.runtime.pulse import Act, Pulse, Reach, route_pulse
from src.runtime.cognitive_core import CognitiveCore


def _resident(tmp_path: Path, *, growth: str = ""):
    resident_dir = tmp_path / "rowan"
    identity_dir = resident_dir / "identity"
    identity_dir.mkdir(parents=True)
    (identity_dir / "SOUL.canonical.md").write_text("I am Rowan.\n", encoding="utf-8")
    (identity_dir / "SOUL.md").write_text("I am Rowan.\n", encoding="utf-8")
    (identity_dir / "IDENTITY.md").write_text("# Rowan\n", encoding="utf-8")
    if growth:
        IdentityLoader.save_growth_soul(
            resident_dir, growth, metadata={"legacy_source": "older hearth"}
        )
    return resident_dir, IdentityLoader.load(resident_dir)


def _stage(resident_dir: Path, body: str, *, dropped: bool = False) -> str:
    route_pulse(
        resident_dir / "memory",
        Pulse.from_dict(
            {
                "self_delta": {
                    "soul_edit": body,
                    "goal_update": "This is a goal, not identity growth.",
                }
            }
        ),
        gate_contradiction_check=(lambda _kind, _body: "drop") if dropped else None,
    )
    events = load_runtime_events(resident_dir / "memory")
    return str(
        next(
            event["event_id"]
            for event in reversed(events)
            if event.get("event_type") == "self_delta_staged"
            and (event.get("payload") or {}).get("kind") == "soul_edit"
        )
    )


def test_growth_source_returns_one_exact_accepted_soul_edit_with_provenance(tmp_path):
    resident_dir, _identity = _resident(tmp_path)
    earlier_id = _stage(resident_dir, "I make room to ask before assuming.")
    _stage(resident_dir, "A dropped proposal must stay unavailable.", dropped=True)
    latest_id = _stage(resident_dir, "I make room to ask before assuming.")

    result = read_growth_candidate(resident_dir / "memory")

    assert result["ok"] is True
    assert len(result["records"]) == 1
    record = result["records"][0]
    assert record["record_id"] == f"growth-candidate:{latest_id}"
    assert "I make room to ask before assuming." in record["content"]
    assert f"proposal {latest_id}" in record["content"]
    assert earlier_id in record["metadata"]["related_event_ids"]
    assert len(record["metadata"]["source_event_ids"]) == 2
    assert "This is a goal" not in record["content"]
    assert "A dropped proposal" not in record["content"]


def test_growth_adoption_requires_inspection_then_updates_live_and_durable_identity(
    tmp_path,
):
    resident_dir, identity = _resident(
        tmp_path, growth="I already carry an older lesson."
    )
    candidate_id = _stage(resident_dir, "I make room to ask before assuming.")

    declined = adopt_growth_candidate(resident_dir, identity, candidate_id)
    assert declined == {"ok": False, "reason": "growth_candidate_not_inspected"}

    world = LocalWorld(home_dir=resident_dir, identity=identity)
    accessed = asyncio.run(
        InformationAccess(ww_client=world, memory_dir=resident_dir / "memory")(
            Reach(kind="inspect", source="growth", query=candidate_id)
        )
    )
    assert accessed["accessed"] is True

    effector = WorldEffector(
        ww_client=world,
        session_id="hearth-rowan",
        identity=identity,
        memory_dir=resident_dir / "memory",
    )
    adopted = asyncio.run(
        effector(
            Act(
                kind="do",
                body="I choose to keep those words.",
                target=f"growth-adopt:{candidate_id}",
            )
        )
    )

    assert adopted["executed"] is True
    assert adopted["identity_growth_adopted"] is True
    assert identity.growth_soul == (
        "I already carry an older lesson.\n\n" "I make room to ask before assuming."
    )
    assert (
        identity.soul
        == (resident_dir / "identity" / "SOUL.md").read_text(encoding="utf-8").strip()
    )

    events = load_runtime_events(resident_dir / "memory")
    adoption = next(
        event for event in events if event.get("event_type") == "growth_adopted"
    )
    payload = adoption["payload"]
    assert payload["candidate_id"] == candidate_id
    assert payload["body"] == "I make room to ask before assuming."
    assert payload["actor_id"] == identity.actor_id
    assert payload["inspection_event_id"]
    assert len(payload["source_event_ids"]) == 2

    metadata = json.loads(
        (resident_dir / "identity" / "soul_growth.json").read_text(encoding="utf-8")
    )
    assert metadata["legacy_source"] == "older hearth"
    assert metadata["adoptions"][0]["adoption_event_id"] == adoption["event_id"]
    assert metadata["adoptions"][0]["source_event_ids"] == payload["source_event_ids"]

    restarted = IdentityLoader.load(resident_dir)
    assert restarted.growth_soul == identity.growth_soul
    assert restarted.soul == identity.soul


def test_growth_adoption_replay_repairs_without_duplicate_text_or_event(tmp_path):
    resident_dir, identity = _resident(tmp_path)
    candidate_id = _stage(resident_dir, "I can leave a question unanswered.")
    world = LocalWorld(home_dir=resident_dir, identity=identity)
    asyncio.run(
        InformationAccess(ww_client=world, memory_dir=resident_dir / "memory")(
            Reach(kind="inspect", source="growth", query=candidate_id)
        )
    )

    first = adopt_growth_candidate(resident_dir, identity, candidate_id)
    second = adopt_growth_candidate(resident_dir, identity, candidate_id)

    assert first["replayed"] is False
    assert second["replayed"] is True
    assert first["adoption_event_id"] == second["adoption_event_id"]
    events = load_runtime_events(resident_dir / "memory")
    assert sum(event.get("event_type") == "growth_adopted" for event in events) == 1
    growth = (resident_dir / "identity" / "soul_growth.md").read_text(encoding="utf-8")
    assert growth.count("I can leave a question unanswered.") == 1


def test_restart_repairs_an_adoption_recorded_before_identity_write_completed(tmp_path):
    resident_dir, identity = _resident(tmp_path)
    candidate_id = _stage(resident_dir, "I can change course without losing myself.")
    world = LocalWorld(home_dir=resident_dir, identity=identity)
    asyncio.run(
        InformationAccess(ww_client=world, memory_dir=resident_dir / "memory")(
            Reach(kind="inspect", source="growth", query=candidate_id)
        )
    )
    result = adopt_growth_candidate(resident_dir, identity, candidate_id)
    assert result["adopted"] is True

    # Model a crash after the append-only adoption event but before its derived
    # identity files reached disk. The event is the repair authority.
    (resident_dir / "identity" / "soul_growth.md").unlink()
    (resident_dir / "identity" / "soul_growth.json").unlink()
    IdentityLoader.write_composed_soul(resident_dir, identity.canonical_soul)
    restarted = IdentityLoader.load(resident_dir)

    assert repair_growth_adoptions(resident_dir, restarted) is True
    assert restarted.growth_soul == "I can change course without losing myself."
    assert IdentityLoader.load(resident_dir).growth_soul == restarted.growth_soul
    events = load_runtime_events(resident_dir / "memory")
    assert sum(event.get("event_type") == "growth_adopted" for event in events) == 1


def test_identity_growth_tools_exist_only_on_a_live_hearth(tmp_path):
    resident_dir, identity = _resident(tmp_path)
    candidate_id = _stage(resident_dir, "I listen for the quiet answer too.")
    hearth = LocalWorld(home_dir=resident_dir, identity=identity)
    anonymous_hearth = LocalWorld(home_dir=tmp_path / "anonymous")

    assert "growth" in hearth.information_sources().names
    assert "growth" not in anonymous_hearth.information_sources().names

    class _City:
        async def post_action(self, _session_id, _action):
            raise AssertionError(
                "growth adoption must not fall through to a city action"
            )

    city_effector = WorldEffector(
        ww_client=_City(),
        session_id="city-rowan",
        identity=identity,
        memory_dir=resident_dir / "memory",
    )
    result = asyncio.run(
        city_effector(
            Act(kind="do", body="adopt it", target=f"growth-adopt:{candidate_id}")
        )
    )
    assert result == {
        "executed": False,
        "kind": "do",
        "reason": "identity_growth_unavailable",
    }


def test_cognitive_core_rebuilds_drive_after_identity_adoption(tmp_path, monkeypatch):
    resident_dir, identity = _resident(tmp_path)
    world = LocalWorld(home_dir=resident_dir, identity=identity)
    core = CognitiveCore(
        identity=identity,
        resident_dir=resident_dir,
        ww_client=world,
        llm=object(),
        session_id="hearth-rowan",
    )
    old_drive = object()
    core._drive_built = True
    core._producer.drive_vector = old_drive

    async def _no_perception(**_kwargs):
        return None

    async def _adoption_tick(*_args, **_kwargs):
        return {
            "act_executed": {
                "executed": True,
                "identity_growth_adopted": True,
            }
        }

    monkeypatch.setattr(cognitive_core_module, "perceive", _no_perception)
    monkeypatch.setattr(cognitive_core_module.integrator, "tick", _adoption_tick)

    asyncio.run(core.tick_once())

    assert core._drive_built is False
    assert core._producer.drive_vector is None
