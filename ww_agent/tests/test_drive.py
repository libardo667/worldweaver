from __future__ import annotations

import asyncio

from src.runtime.drive import DeterministicEmbedder, DriveVector


def _build(**kw) -> DriveVector:
    return asyncio.run(DriveVector.build(embedder=DeterministicEmbedder(), **kw))


# A mechanic and a drifter — two distinct constitutions.
MECHANIC = "I mend broken engines with steady hands. I have no patience for idle talk."
DRIFTER = "I drift through the fog and listen to the harbor at dawn. I dwell in weather and mood."


def test_distinct_souls_resonate_with_different_moments():
    mechanic = _build(constitution=MECHANIC)
    drifter = _build(constitution=DRIFTER)

    engine_moment = "a broken engine sits cold in the yard"
    fog_moment = "fog rolls off the harbor at dawn"

    rm_e = asyncio.run(mechanic.resonance(engine_moment))
    rd_e = asyncio.run(drifter.resonance(engine_moment))
    rm_f = asyncio.run(mechanic.resonance(fog_moment))
    rd_f = asyncio.run(drifter.resonance(fog_moment))

    # The mechanic is pulled harder by the broken engine; the drifter by the fog.
    assert rm_e["magnitude"] > rd_e["magnitude"]
    assert rd_f["magnitude"] > rm_f["magnitude"]
    # And each surfaces its own fragment, not the other's.
    assert "engine" in rm_e["resonant"][0]["text"].lower()
    assert "fog" in rd_f["resonant"][0]["text"].lower() or "harbor" in rd_f["resonant"][0]["text"].lower()


def test_constitution_dominates_growth_and_reverie():
    # Same fragment in both the constitution and a reverie — the constitution
    # (weight 1.0) should win over the reverie (0.35).
    dv = _build(constitution="the harbor is my whole home", reveries=["the harbor is my whole home"])
    r = asyncio.run(dv.resonance("the harbor is my whole home"))
    assert r["resonant"][0]["slice"] == "constitution"


def test_contradiction_check_floors_on_constitution():
    dv = _build(constitution=MECHANIC)
    # An edit grounded in the core resonates → accepted (None).
    assert asyncio.run(dv.contradiction_check("soul_edit", "I take pride in mending broken engines")) is None
    # An edit with no footing in the constitution → tempered.
    assert asyncio.run(dv.contradiction_check("soul_edit", "I float away on cosmic tides forever")) == "clamp"


def test_empty_drive_vector_is_neutral():
    dv = _build(constitution="")
    assert dv.is_empty()
    r = asyncio.run(dv.resonance("anything at all happening here"))
    assert r["magnitude"] == 0.0 and r["resonant"] == []
    # A neutral drive vector never blocks self_delta.
    assert asyncio.run(dv.contradiction_check("soul_edit", "anything")) == "clamp"


def test_slices_are_embedded_and_fragmented():
    dv = _build(constitution=MECHANIC, growth="I have learned to listen before I wrench.", reveries=["the smell of motor oil at dawn"])
    assert len(dv.slices["constitution"]) == 2  # two sentences
    assert len(dv.slices["growth"]) == 1
    assert len(dv.slices["reverie"]) == 1
    # Embeddings are unit vectors.
    _, vec = dv.slices["constitution"][0]
    assert abs(sum(x * x for x in vec) - 1.0) < 1e-6
