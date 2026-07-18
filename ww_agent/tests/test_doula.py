from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.runtime.doula import DoulaLoop, EntityClass, ProximityCheck, _SpawnLedger
from src.identity.hearth_manifest import load_hearth_manifest
from src.runtime.ledger import load_runtime_events
from src.world.client import WorldFact


class _DummyWorldClient:
    async def get_nearby_landmarks(self, location: str, radius_km: float = 0.75):
        return []

    async def get_grounding(self):
        return {}


class _DummyInferenceClient:
    async def complete(self, *args, **kwargs):
        return "Placeholder"


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
    assert any(item["name"] == "Western Addition" and item["reason"] == "static_place" for item in decisions)
    assert any(item["name"] == "Darnell" and item["reason"] == "already_tethered" for item in decisions)


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
            "total_present": 1,
            "total_agents": 0,
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


def test_vitality_bootstrap_skips_neighborhoods_with_resting_residents(tmp_path, monkeypatch):
    doula = _make_doula(tmp_path)
    doula._neighborhood_vitality = {
        "Inner Richmond": {
            "name": "Inner Richmond",
            "vitality_score": 0.35,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 1,
            "total_agents": 1,
            "needs_residents": True,
        }
    }

    seeded: list[tuple[str, list[str]]] = []

    async def fake_seed(location: str, context_lines: list[str]):
        seeded.append((location, context_lines))

    monkeypatch.setattr(doula, "_seed_founding_resident", fake_seed)

    result = asyncio.run(doula._maybe_bootstrap_vitality_gap())

    assert result is False
    assert seeded == []


def test_vitality_bootstrap_respects_recent_spawn_cooldown(tmp_path, monkeypatch):
    doula = _make_doula(tmp_path)
    doula._neighborhood_vitality = {
        "Inner Richmond": {
            "name": "Inner Richmond",
            "vitality_score": 0.35,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 0,
            "total_agents": 0,
            "needs_residents": True,
        },
        "Outer Sunset": {
            "name": "Outer Sunset",
            "vitality_score": 0.4,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 0,
            "total_agents": 0,
            "needs_residents": True,
        },
    }
    doula._record_decision(
        name="Rosa Garza",
        kind="spawned",
        reason="resident_scaffolded",
        entity_class=EntityClass.NOVEL.value,
        location="Inner Richmond",
    )

    seeded: list[tuple[str, list[str]]] = []

    async def fake_seed(location: str, context_lines: list[str]):
        seeded.append((location, context_lines))

    monkeypatch.setattr(doula, "_seed_founding_resident", fake_seed)

    result = asyncio.run(doula._maybe_bootstrap_vitality_gap())

    assert result is True
    assert seeded
    assert seeded[0][0] == "Outer Sunset"


def test_founding_cohort_bootstrap_seeds_multiple_empty_neighborhoods(tmp_path, monkeypatch):
    doula = _make_doula(tmp_path)
    doula._tethered.clear()
    doula._neighborhood_vitality = {
        "Outer Sunset": {
            "name": "Outer Sunset",
            "vitality_score": 0.2,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 0,
            "total_agents": 0,
            "needs_residents": False,
        },
        "Inner Richmond": {
            "name": "Inner Richmond",
            "vitality_score": 0.3,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 0,
            "total_agents": 0,
            "needs_residents": False,
        },
        "Chinatown": {
            "name": "Chinatown",
            "vitality_score": 0.4,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 0,
            "total_agents": 0,
            "needs_residents": False,
        },
    }

    seeded: list[str] = []

    async def fake_seed(location: str, context_lines: list[str]):
        seeded.append(location)
        doula._record_decision(
            name=f"Resident {len(seeded)}",
            kind="spawned",
            reason="resident_scaffolded",
            entity_class=EntityClass.NOVEL.value,
            location=location,
        )
        doula._tethered.add(f"resident-{len(seeded)}")
        return True

    monkeypatch.setattr(doula, "_seed_founding_resident", fake_seed)

    result = asyncio.run(doula._maybe_bootstrap_founding_cohort())

    assert result is True
    assert seeded == ["Outer Sunset", "Inner Richmond", "Chinatown"]


def test_gentle_expansion_bootstrap_seeds_one_neighborhood_after_founding_floor(tmp_path, monkeypatch):
    doula = _make_doula(tmp_path)
    doula._tethered.clear()
    doula._neighborhood_vitality = {
        "Outer Sunset": {
            "name": "Outer Sunset",
            "vitality_score": 0.2,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 0,
            "total_agents": 0,
            "needs_residents": False,
        },
        "Inner Richmond": {
            "name": "Inner Richmond",
            "vitality_score": 0.3,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 0,
            "total_agents": 0,
            "needs_residents": False,
        },
        "Chinatown": {
            "name": "Chinatown",
            "vitality_score": 0.4,
            "current_present": 0,
            "current_agents": 0,
            "total_present": 0,
            "total_agents": 0,
            "needs_residents": False,
        },
    }
    for idx in range(6):
        resident = doula._residents_dir / f"resident_{idx}"
        resident.mkdir(parents=True, exist_ok=True)
        doula._tethered.add(f"resident-{idx}")
    doula._record_decision(
        name="Recent Spawn",
        kind="spawned",
        reason="resident_scaffolded",
        entity_class=EntityClass.NOVEL.value,
        location="Outer Sunset",
    )

    seeded: list[str] = []

    async def fake_seed(location: str, context_lines: list[str]):
        seeded.append(location)
        return True

    monkeypatch.setattr(doula, "_seed_founding_resident", fake_seed)

    result = asyncio.run(doula._maybe_bootstrap_gentle_expansion())

    assert result is True
    assert seeded == ["Inner Richmond"]


def test_seed_and_spawn_uses_neighborhood_as_home_location(tmp_path):
    residents_dir = tmp_path / "residents"
    residents_dir.mkdir(parents=True, exist_ok=True)

    class _World(_DummyWorldClient):
        async def get_nearby_landmarks(self, location: str, radius_km: float = 0.75):
            return ["Clement Street"]

    class _LLM(_DummyInferenceClient):
        def __init__(self):
            self.calls = 0

        async def complete(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return "Soul paragraph"
            if self.calls == 2:
                return "Identity paragraph"
            return "Rosa Garza"

    doula = DoulaLoop(
        ww_client=_World(),
        llm=_LLM(),
        residents_dir=residents_dir,
        spawn_queue=asyncio.Queue(),
        tethered_names=set(),
        known_session_ids=[],
    )

    asyncio.run(
        doula._seed_and_spawn(
            "Rosa Garza",
            ["She belongs to Outer Sunset.", "She keeps the block in her bones."],
            entry_location="Clement Street",
            home_location="Outer Sunset",
            entity_class=EntityClass.NOVEL,
        )
    )

    identity_dir = residents_dir / "rosa_garza" / "identity"
    tuning = json.loads((identity_dir / "tuning.json").read_text(encoding="utf-8"))
    identity_md = (identity_dir / "IDENTITY.md").read_text(encoding="utf-8")
    entry_location = (identity_dir / "entry_location.txt").read_text(encoding="utf-8").strip()

    assert tuning["home_location"] == "Outer Sunset"
    assert entry_location == "Clement Street"
    assert "home_location" in identity_md


def test_seed_records_provenance_and_one_cohort_config(tmp_path, monkeypatch):
    residents_dir = tmp_path / "residents"
    residents_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("WW_DOULA_MODELS", "seed-a, seed-b")
    monkeypatch.setenv("WW_ACTION_TENDENCY", "1")
    monkeypatch.setenv("WW_DOULA_HAND_ONLY", "1")
    monkeypatch.setenv("WW_INCUBATION_ENABLED", "true")

    doula = DoulaLoop(
        ww_client=_DummyWorldClient(),
        llm=_DummyInferenceClient(),
        residents_dir=residents_dir,
        spawn_queue=asyncio.Queue(),
        tethered_names=set(),
        known_session_ids=[],
        poll_interval_seconds=45.0,
        max_spawns_per_day=3,
        soul_model="configured-seed",
    )

    asyncio.run(
        doula._seed_and_spawn(
            "Rosa Garza",
            ["She lives in Outer Sunset."],
            entry_location="Clement Street",
            home_location="Outer Sunset",
            first_landmark_target="Clement Street",
            model="seed-a",
            dealt_hand="- heritage: a Mexican background",
            dealt_hand_fields={
                "heritage": "a Mexican background",
                "age": "in her thirties",
                "temperament": "blunt and plainspoken",
                "social_disposition": "born forward",
                "origin": "raised by a grandparent",
            },
        )
    )
    asyncio.run(
        doula._seed_and_spawn(
            "Mina Park",
            ["Mina repairs watches."],
            entry_location="Chinatown",
            entity_class=EntityClass.PLAYER_SHADOW,
            model="seed-b",
        )
    )

    rosa_dir = residents_dir / "rosa_garza"
    rosa_events = load_runtime_events(rosa_dir / "memory")
    seeded = next(event for event in rosa_events if event["event_type"] == "resident_seeded")
    payload = seeded["payload"]

    assert payload["schema_version"] == 1
    assert payload["actor_id"] == (rosa_dir / "identity" / "resident_id.txt").read_text(encoding="utf-8").strip()
    assert payload["resident_slug"] == "rosa_garza"
    assert payload["seed_model"] == "seed-a"
    assert payload["doula_mode"] == "dealt_hand"
    assert payload["hand_only_context"] is True
    assert payload["dealt_hand"]["temperament"] == "blunt and plainspoken"
    assert payload["home_location"] == "Outer Sunset"
    assert payload["first_landmark_target"] == "Clement Street"

    mina_events = load_runtime_events(residents_dir / "mina_park" / "memory")
    mina_seeded = next(event for event in mina_events if event["event_type"] == "resident_seeded")
    assert mina_seeded["payload"]["doula_mode"] == "narrative_evidence"
    assert mina_seeded["payload"]["dealt_hand"] == {}
    assert mina_seeded["payload"]["cohort_id"] == payload["cohort_id"]

    cohort_events = load_runtime_events(residents_dir / ".doula_runtime" / "memory")
    cohort_configs = [event for event in cohort_events if event["event_type"] == "cohort_config"]
    assert len(cohort_configs) == 1
    config = cohort_configs[0]["payload"]
    assert config["cohort_id"] == payload["cohort_id"]
    assert config["venture"]["action_tendency_enabled"] is True
    assert config["model"]["seed_model_pool"] == ["seed-a", "seed-b"]
    assert config["window"] == {
        "scan_poll_interval_seconds": 45.0,
        "spawn_rate_window_hours": 24,
        "max_spawns_per_window": 3,
    }
    assert config["isolation"]["incubation_enabled"] is True


def test_seed_founding_resident_bootstraps_at_home_location_and_keeps_landmark_hint(tmp_path):
    residents_dir = tmp_path / "residents"
    residents_dir.mkdir(parents=True, exist_ok=True)

    class _World(_DummyWorldClient):
        async def get_nearby_landmarks(self, location: str, radius_km: float = 0.75):
            return ["Clement Street"]

    class _LLM(_DummyInferenceClient):
        def __init__(self):
            self.calls = 0

        async def complete(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return "Rosa Garza"
            if self.calls == 2:
                return "Soul paragraph"
            return "Identity paragraph"

    doula = DoulaLoop(
        ww_client=_World(),
        llm=_LLM(),
        residents_dir=residents_dir,
        spawn_queue=asyncio.Queue(),
        tethered_names=set(),
        known_session_ids=[],
    )

    result = asyncio.run(
        doula._seed_founding_resident(
            "Outer Sunset",
            ["She belongs to Outer Sunset.", "She keeps the block in her bones."],
        )
    )

    assert result is True
    identity_dir = residents_dir / "rosa_garza" / "identity"
    tuning = json.loads((identity_dir / "tuning.json").read_text(encoding="utf-8"))
    identity_md = (identity_dir / "IDENTITY.md").read_text(encoding="utf-8")
    entry_location = (identity_dir / "entry_location.txt").read_text(encoding="utf-8").strip()

    assert tuning["home_location"] == "Outer Sunset"
    assert tuning["first_landmark_target"] == "Clement Street"
    assert entry_location == "Outer Sunset"
    assert "nearby_landmark" in identity_md


def test_fixed_creation_seeds_a_hand_only_dormant_hearth(tmp_path):
    residents_dir = tmp_path / "residents"
    residents_dir.mkdir(parents=True, exist_ok=True)
    queue: asyncio.Queue = asyncio.Queue()
    tethered: set[str] = set()

    class _World(_DummyWorldClient):
        async def get_nearby_landmarks(self, location: str, radius_km: float = 0.75):
            return ["A neighborhood cafe"]

        async def get_world_facts(self, *args, **kwargs):
            raise AssertionError("hand-only creation must not query city history")

        async def get_graph_facts(self, *args, **kwargs):
            raise AssertionError("hand-only creation must not query the city graph")

    class _LLM(_DummyInferenceClient):
        def __init__(self):
            self.calls = 0

        async def complete(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return "Nora Flores"
            if self.calls == 2:
                return "Nora teaches violin and hates sweet coffee."
            return "Nora Flores is a violin teacher with strong opinions about coffee."

    doula = DoulaLoop(
        ww_client=_World(),
        llm=_LLM(),
        residents_dir=residents_dir,
        spawn_queue=queue,
        tethered_names=tethered,
        known_session_ids=[],
        creation_mode="fixed_dormant_batch",
    )

    created = asyncio.run(
        doula._seed_founding_resident(
            "Woodstock",
            ["This person lives around Woodstock."],
            vocation_domain="teaching and tutoring — preschool teacher, ESL tutor, music teacher, swim coach",
            dormant=True,
            hand_only_context=True,
        )
    )

    home = residents_dir / "nora_flores"
    assert created is True
    assert queue.empty()
    assert tethered == set()
    assert not (residents_dir / ".doula_spawns.json").exists()
    assert load_hearth_manifest(home).actor_id == (home / "identity" / "resident_id.txt").read_text(encoding="utf-8").strip()
    seeded = next(event for event in load_runtime_events(home / "memory") if event["event_type"] == "resident_seeded")
    assert seeded["payload"]["creation_mode"] == "fixed_dormant_batch"
    assert seeded["payload"]["dormant"] is True
    assert seeded["payload"]["hand_only_context"] is True
    assert seeded["payload"]["dealt_hand"]["livelihood_domain"].startswith("teaching and tutoring")


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
    monkeypatch.setattr("src.runtime.doula.random.random", lambda: 0.5)

    chronotype = doula._infer_chronotype(
        name="Lena Quiros",
        context_lines=["A practical neighbor with no obvious schedule cues."],
        entry_location="South Tabor",
        entity_class=EntityClass.NOVEL,
    )

    assert chronotype == "day"
