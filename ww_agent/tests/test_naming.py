from __future__ import annotations

import asyncio
from pathlib import Path

from src.loops.doula import DoulaLoop
from src.runtime.naming import slugify_resident_name


class _DummyWorldClient:
    pass


class _StubInferenceClient:
    async def complete(self, *args, **kwargs):
        return "A steady soul."


def test_slugify_resident_name_normalizes_human_display_names():
    assert slugify_resident_name("Diana Chen") == "diana_chen"
    assert slugify_resident_name("  Camila Vega  ") == "camila_vega"
    assert slugify_resident_name("Élodie 7") == "elodie_7"
    assert slugify_resident_name("7 of 9") == "resident_7_of_9"


def test_doula_scaffolds_slugged_resident_directory(tmp_path, monkeypatch):
    residents_dir = tmp_path / "residents"
    residents_dir.mkdir(parents=True, exist_ok=True)
    spawn_queue: asyncio.Queue[Path] = asyncio.Queue()
    doula = DoulaLoop(
        ww_client=_DummyWorldClient(),
        llm=_StubInferenceClient(),
        residents_dir=residents_dir,
        spawn_queue=spawn_queue,
        tethered_names=set(),
        known_session_ids=[],
    )

    async def fake_world_facts(_query: str):
        return []

    async def fake_graph_facts(_query: str):
        return []

    monkeypatch.setattr(doula, "_safe_get_world_facts", fake_world_facts)
    monkeypatch.setattr(doula, "_safe_get_graph_facts", fake_graph_facts)

    asyncio.run(
        doula._seed_and_spawn(
            "Diana Chen",
            ["Diana runs a tea stall."],
            entry_location="Inner Richmond",
        )
    )

    resident_dir = residents_dir / "diana_chen"
    assert resident_dir.exists()
    assert (resident_dir / "identity" / "SOUL.md").exists()
    assert (resident_dir / "identity" / "IDENTITY.md").exists()
    assert asyncio.run(spawn_queue.get()) == resident_dir
