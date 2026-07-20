from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _probe_module():
    path = (
        Path(__file__).resolve().parents[2] / "research" / "probes" / "reciprocity.py"
    )
    spec = importlib.util.spec_from_file_location("reciprocity_probe", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_ledger(root: Path, resident: str, events: list[dict]) -> None:
    resident_dir = root / "residents" / resident
    (resident_dir / "identity").mkdir(parents=True)
    (resident_dir / "identity" / "IDENTITY.md").write_text(
        f"# {resident.title()}\n", encoding="utf-8"
    )
    memory_dir = resident_dir / "memory"
    memory_dir.mkdir()
    (memory_dir / "runtime_ledger.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )


def test_reciprocity_probe_reads_prompt_delivery_and_co_present_edges(tmp_path):
    _write_ledger(
        tmp_path,
        "alix",
        [
            {
                "event_type": "chat_sent",
                "payload": {
                    "edge_schema_version": 1,
                    "actor_id": "actor-alix",
                    "actor_session_id": "alix-1",
                    "location": "Market",
                    "co_present": ["actor-bea"],
                    "utterance_id": "chat:Market:101",
                    "transport_id": "101",
                    "addressed": "Bea",
                    "addressed_actor_id": "actor-bea",
                },
            }
        ],
    )
    _write_ledger(
        tmp_path,
        "bea",
        [
            {
                "event_type": "utterance_perceived",
                "payload": {
                    "edge_schema_version": 1,
                    "actor_id": "actor-bea",
                    "actor_session_id": "bea-1",
                    "location": "Market",
                    "co_present": ["actor-alix"],
                    "utterance_id": "chat:Market:101",
                    "transport_id": "101",
                    "speaker_actor_id": "actor-alix",
                    "speaker_session_id": "alix-1",
                    "speaker_name": "Alix",
                    "channel": "local",
                    "is_direct": True,
                },
            },
            {
                "event_type": "chat_sent",
                "payload": {
                    "reply_to_utterance_id": "chat:Market:101",
                    "in_reply_to": "101",
                },
            },
        ],
    )

    probe = _probe_module()
    perceived = probe.perceived_conditioned(tmp_path)
    opportunity = probe.opportunity_conditioned(tmp_path)

    assert perceived["perceived_overtures"] == 1
    assert perceived["answered"] == 1
    assert opportunity == {
        "opportunities": 1,
        "answered": 1,
        "rate_pct": 100.0,
        "available": True,
    }
