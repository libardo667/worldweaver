from __future__ import annotations

from src.runtime.ledger import load_runtime_events
from src.runtime.memory import derive_memories, memories
from src.runtime.pulse import Pulse, route_pulse


def _events_kept(memory_dir):
    return [e for e in load_runtime_events(memory_dir) if e.get("event_type") == "memory_kept"]


def test_pulse_parses_keep_as_string_list_or_objects():
    assert [k.note for k in Pulse.from_dict({"keep": "the keeper moves to NL"}).keepsakes] == ["the keeper moves to NL"]
    assert [k.note for k in Pulse.from_dict({"keep": ["a", "b"]}).keepsakes] == ["a", "b"]
    assert [k.note for k in Pulse.from_dict({"keep": [{"note": "x"}, {"text": "y"}, {"note": ""}]}).keepsakes] == ["x", "y"]
    assert Pulse.from_dict({"felt_sense": "hi"}).keepsakes == []  # absent → none


def test_route_pulse_writes_memory_kept_events(tmp_path):
    pulse = Pulse.from_dict({"felt_sense": "noted", "keep": ["the keeper is moving to the Netherlands", "I started a Threshold Log"]})
    summary = route_pulse(tmp_path, pulse, now="2026-06-03T00:00:00+00:00")
    assert summary["memories_kept"] == 2
    assert {e["payload"]["note"] for e in _events_kept(tmp_path)} == {"the keeper is moving to the Netherlands", "I started a Threshold Log"}


def test_derive_memories_newest_first_and_dedupes_on_rekeep(tmp_path):
    for i, note in enumerate(["one", "two", "one"]):  # 'one' kept again, latest
        route_pulse(tmp_path, Pulse.from_dict({"keep": [note]}), now=f"2026-06-03T00:0{i}:00+00:00")
    notes = [m["note"] for m in memories(tmp_path)]
    assert notes == ["one", "two"]  # 'one' re-keyed → back to top; no duplicate


def test_derive_memories_caps_at_limit(tmp_path):
    for i in range(20):
        route_pulse(tmp_path, Pulse.from_dict({"keep": [f"note-{i:02d}"]}), now=f"2026-06-03T00:{i:02d}:00+00:00")
    kept = derive_memories(load_runtime_events(tmp_path), limit=5)
    assert len(kept) == 5 and kept[0]["note"] == "note-19"  # newest five


def test_kept_memory_survives_ledger_eviction(tmp_path):
    # the bug this fixes: the rolling ledger is hard-capped and evicts old events.
    # a kept memory must outlive that — route_pulse writes it to the durable store,
    # so even if the ledger loses the event entirely, the memory persists.
    from src.runtime.memory import KEPT_STORE_NAME

    route_pulse(tmp_path, Pulse.from_dict({"keep": ["the keeper moves to NL in autumn"]}), now="2026-06-03T00:00:00+00:00")
    assert (tmp_path / KEPT_STORE_NAME).exists()
    (tmp_path / "runtime_ledger.jsonl").write_text("", encoding="utf-8")  # simulate full eviction
    assert [m["note"] for m in memories(tmp_path)] == ["the keeper moves to NL in autumn"]


def test_memories_rescues_a_ledger_only_keepsake_into_the_durable_store(tmp_path):
    # a pre-fix memory that exists ONLY in the rolling ledger is migrated into the
    # durable store on read, so it survives the next eviction.
    from src.runtime.ledger import append_runtime_event
    from src.runtime.memory import KEPT_STORE_NAME

    append_runtime_event(tmp_path, event_type="memory_kept", payload={"note": "an old morning thought", "kept_ts": "2026-06-03T08:00:00+00:00"})
    assert not (tmp_path / KEPT_STORE_NAME).exists()
    assert "an old morning thought" in [m["note"] for m in memories(tmp_path)]  # read rescues it
    assert (tmp_path / KEPT_STORE_NAME).exists()
    (tmp_path / "runtime_ledger.jsonl").write_text("", encoding="utf-8")
    assert "an old morning thought" in [m["note"] for m in memories(tmp_path)]  # still here after eviction


# --- relevance recall (the drive-vector's mechanism over the memory store) ---

import asyncio  # noqa: E402

from src.runtime.drive import DeterministicEmbedder  # noqa: E402
from src.runtime.memory import MemoryRecall  # noqa: E402


def test_memory_recall_ranks_by_relevance_not_recency():
    notes = [
        "the keeper is moving to the Netherlands among the windmills",  # newest would be last
        "the printer clicks in its sleep so i remain wary always",
        "a copper button gathers warmth beside the cooling hearth",
    ]
    mr = MemoryRecall(DeterministicEmbedder())
    hits = asyncio.run(mr.recall(notes, "tell me about the Netherlands windmills and the keeper"))
    assert hits and hits[0]["note"] == notes[0]  # relevance wins, not the most recent
    assert notes[1] not in [h["note"] for h in hits[:1]]  # the unrelated printer note doesn't lead


def test_memory_recall_empty_without_moment_or_notes():
    mr = MemoryRecall(DeterministicEmbedder())
    assert asyncio.run(mr.recall([], "anything")) == []
    assert asyncio.run(mr.recall(["a kept note"], "")) == []


def test_memory_recall_caches_embeddings_per_note():
    mr = MemoryRecall(DeterministicEmbedder())
    asyncio.run(mr.recall(["the rain is thin today", "the dust drifts here"], "rain on the glass"))
    assert "the rain is thin today" in mr._cache and "the dust drifts here" in mr._cache


def test_memory_recall_diversity_avoids_near_dup_pileup():
    # the offline embedder is exact-token, so the distinct note must share an actual
    # word ("netherlands") with the moment to be relevant at all.
    near = [
        "the keeper moving to the netherlands soon certain packing",
        "the keeper moving to the netherlands close certain packing",
        "the keeper moving to the netherlands looms certain packing",
    ]
    distinct = "the netherlands famous tulips canals windmills bicycles"
    notes = near + [distinct]
    moment = "the keeper moving to the netherlands"
    div = [h["note"] for h in asyncio.run(MemoryRecall(DeterministicEmbedder()).recall(notes, moment, top_k=2, diversity=0.85))]
    rel = [h["note"] for h in asyncio.run(MemoryRecall(DeterministicEmbedder()).recall(notes, moment, top_k=2, diversity=0.0))]
    assert distinct in div  # diversity surfaces the genuinely different recollection
    assert distinct not in rel and all(n in near for n in rel)  # pure relevance piles up near-dups


def test_memory_novel_drops_restatements_keeps_distinct():
    mr = MemoryRecall(DeterministicEmbedder())
    existing = ["the keeper is moving to the netherlands soon"]
    cands = ["the keeper is moving to the netherlands very soon indeed", "the printer makes a clicking sound at night"]
    kept = asyncio.run(mr.novel(cands, existing, threshold=0.78))
    assert cands[0] not in kept  # a near-restatement of an existing memory is dropped
    assert cands[1] in kept  # a genuinely different fact is kept


def test_memory_novel_drops_dups_within_the_batch():
    mr = MemoryRecall(DeterministicEmbedder())
    cands = ["the groove is worn so stop polishing the same shape", "the groove is worn so quit polishing that same shape"]
    kept = asyncio.run(mr.novel(cands, [], threshold=0.78))
    assert len(kept) == 1  # two restatements of one self-instruction → one survives
