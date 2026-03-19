from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.loops.doula import DoulaLoop, EntityClass, ProximityCheck, _SpawnLedger
from src.world.client import WorldFact


class _DummyWorldClient:
    pass


class _DummyInferenceClient:
    pass


def _make_doula(tmp_path: Path) -> DoulaLoop:
    residents_dir = tmp_path / "residents"
    residents_dir.mkdir(parents=True, exist_ok=True)
    return DoulaLoop(
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        residents_dir=residents_dir,
        spawn_queue=asyncio.Queue(),
        tethered_names={"darnell"},
        known_session_ids=[],
    )


def test_find_untethered_names_filters_known_places(tmp_path, monkeypatch):
    doula = _make_doula(tmp_path)
    doula._place_names_cache = {"Western Addition", "Chinatown"}

    async def fake_graph_facts(_query: str):
        return [
            WorldFact(summary="Western Addition came up again.", subject="Western Addition", confidence=1.0),
            WorldFact(summary="Marco was spotted near the park.", subject="Marco", confidence=0.7),
            WorldFact(summary="Darnell spoke with someone nearby.", subject="Darnell", confidence=0.9),
        ]

    async def fake_world_facts(_query: str):
        return [
            WorldFact(summary="Marco was seen lingering by the bus stop."),
            WorldFact(summary="Western Addition was especially busy today."),
        ]

    monkeypatch.setattr(doula, "_safe_get_graph_facts", fake_graph_facts)
    monkeypatch.setattr(doula, "_safe_get_world_facts", fake_world_facts)

    candidates = asyncio.run(doula._find_untethered_names())

    assert [name for name, _, _ in candidates] == ["Marco"]

    decisions = json.loads((doula._decision_log_path).read_text(encoding="utf-8"))
    assert any(
        item["name"] == "Western Addition" and item["reason"] == "static_place"
        for item in decisions
    )
    assert any(
        item["name"] == "Darnell" and item["reason"] == "already_tethered"
        for item in decisions
    )


def test_record_decision_persists_capped_history(tmp_path):
    doula = _make_doula(tmp_path)

    for idx in range(205):
        doula._record_decision(
            name=f"candidate-{idx}",
            kind="skip",
            reason="static_place",
            weight=0.5,
        )

    decisions = json.loads((doula._decision_log_path).read_text(encoding="utf-8"))

    assert len(decisions) == 200
    assert decisions[0]["name"] == "candidate-5"
    assert decisions[-1]["name"] == "candidate-204"


def test_spawn_readiness_requires_threshold(tmp_path):
    doula = _make_doula(tmp_path)

    readiness = doula._score_spawn_readiness(
        weight=0.2,
        entity_class=EntityClass.NOVEL,
        proximity=ProximityCheck(status="near", location="Chinatown"),
        location="Chinatown",
    )

    assert readiness.decision == "below_threshold"
    assert readiness.score < readiness.threshold
    assert readiness.tie_break_probability == 0.0


def test_spawn_readiness_uses_small_tie_break_after_threshold(tmp_path):
    doula = _make_doula(tmp_path)

    readiness = doula._score_spawn_readiness(
        weight=0.9,
        entity_class=EntityClass.PLAYER_SHADOW,
        proximity=ProximityCheck(status="near", location="Chinatown"),
        location="Chinatown",
    )

    assert readiness.decision == "ready"
    assert readiness.score >= readiness.threshold
    assert 0.25 <= readiness.tie_break_probability <= 0.9
    assert readiness.components["proximity_bonus"] > 0.0
    assert readiness.components["shadow_bonus"] > 0.0


def test_spawn_readiness_uses_neighborhood_vitality_signals(tmp_path):
    doula = _make_doula(tmp_path)
    doula._neighborhood_vitality = {
        "Chinatown": {
            "name": "Chinatown",
            "vitality_score": 0.4,
            "current_present": 1,
            "current_agents": 0,
            "current_humans": 1,
            "needs_residents": True,
        }
    }

    readiness = doula._score_spawn_readiness(
        weight=0.35,
        entity_class=EntityClass.NOVEL,
        proximity=ProximityCheck(status="near", location="Chinatown"),
        location="Chinatown",
    )

    assert readiness.decision == "ready"
    assert readiness.components["needs_residents_bonus"] > 0.0
    assert readiness.components["low_vitality_bonus"] > 0.0
    assert readiness.components["agent_saturation_penalty"] == 0.0


def test_vitality_bootstrap_seeds_when_no_candidates_fit(tmp_path, monkeypatch):
    doula = _make_doula(tmp_path)
    doula._neighborhood_vitality = {
        "Inner Richmond": {
            "name": "Inner Richmond",
            "vitality_score": 0.35,
            "current_present": 0,
            "current_agents": 0,
            "needs_residents": True,
        }
    }

    seeded: list[tuple[str, list[str]]] = []

    async def fake_seed(location: str, context_lines: list[str]):
        seeded.append((location, context_lines))

    monkeypatch.setattr(doula, "_seed_founding_resident", fake_seed)

    result = asyncio.run(doula._maybe_bootstrap_vitality_gap())

    assert result is True
    assert seeded
    assert seeded[0][0] == "Inner Richmond"


def test_doula_rebalances_novel_spawn_out_of_saturated_location(tmp_path):
    doula = _make_doula(tmp_path)
    doula._neighborhood_vitality = {
        "Parkside": {
            "name": "Parkside",
            "vitality_score": 2.4,
            "current_present": 5,
            "current_agents": 2,
            "needs_residents": False,
        },
        "Outer Sunset": {
            "name": "Outer Sunset",
            "vitality_score": 0.3,
            "current_present": 0,
            "current_agents": 0,
            "needs_residents": True,
        },
        "Inner Richmond": {
            "name": "Inner Richmond",
            "vitality_score": 0.7,
            "current_present": 1,
            "current_agents": 0,
            "needs_residents": True,
        },
    }

    assert doula._rebalance_entry_location("Parkside", entity_class=EntityClass.NOVEL) == "Outer Sunset"
    assert doula._rebalance_entry_location("Parkside", entity_class=EntityClass.PLAYER_SHADOW) == "Parkside"


def test_spawn_ledger_uses_rolling_24h_window(tmp_path):
    ledger = _SpawnLedger(tmp_path / ".doula_spawns.json", max_per_day=5)
    now = datetime(2026, 3, 18, 0, 16, tzinfo=timezone.utc)

    for idx in range(5):
        ledger.record_spawn(now=now - timedelta(hours=23, minutes=59, seconds=idx))

    assert ledger.can_spawn(now=now) is False
    assert ledger.can_spawn(now=now + timedelta(minutes=2)) is True


def test_spawn_ledger_reads_legacy_date_bucket_format(tmp_path):
    path = tmp_path / ".doula_spawns.json"
    path.write_text(
        json.dumps(
            {
                "2026-03-18": 5,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    ledger = _SpawnLedger(path, max_per_day=5)

    assert ledger.can_spawn(now=datetime(2026, 3, 18, 0, 16, tzinfo=timezone.utc)) is False


def test_doula_infers_early_chronotype_from_bakery_context(tmp_path):
    doula = _make_doula(tmp_path)

    chronotype = doula._infer_chronotype(
        name="Sun Li",
        context_lines=["Runs a tea stall and bakery cart in Chinatown before the morning rush."],
        entry_location="Chinatown",
        entity_class=EntityClass.NOVEL,
    )

    assert chronotype == "early"


def test_doula_infers_night_chronotype_from_night_shift_context(tmp_path):
    doula = _make_doula(tmp_path)

    chronotype = doula._infer_chronotype(
        name="Darnell",
        context_lines=["He is the night clerk at a hotel and works the overnight shift."],
        entry_location="Civic Center",
        entity_class=EntityClass.NOVEL,
    )

    assert chronotype == "night"


def test_doula_falls_back_to_reasonable_default_distribution(tmp_path, monkeypatch):
    doula = _make_doula(tmp_path)
    monkeypatch.setattr("src.loops.doula.random.random", lambda: 0.5)

    chronotype = doula._infer_chronotype(
        name="Lena Quiros",
        context_lines=["A practical neighbor with no obvious schedule cues."],
        entry_location="South Tabor",
        entity_class=EntityClass.NOVEL,
    )

    assert chronotype == "day"
