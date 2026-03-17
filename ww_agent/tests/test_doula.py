from __future__ import annotations

import asyncio
import json
from pathlib import Path

from src.loops.doula import DoulaLoop
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
