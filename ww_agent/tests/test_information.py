from __future__ import annotations

import asyncio

from src.runtime.information import InformationAccess
from src.runtime.ledger import load_runtime_events
from src.runtime.pulse import Reach


class _World:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    async def access_information(self, *, kind: str, source: str, query: str = ""):
        self.requests.append({"kind": kind, "source": source, "query": query})
        return {
            "ok": True,
            "provenance": "local-knowledge",
            "result": "The corner bakery opens before dawn.",
        }


def test_information_access_is_private_ledger_evidence_not_a_world_act(tmp_path):
    world = _World()
    access = InformationAccess(ww_client=world, memory_dir=tmp_path)

    result = asyncio.run(access(Reach(kind="inspect", source="eats", query="North Beach")))

    assert result["accessed"] is True
    assert result["detail"] == "The corner bakery opens before dawn."
    assert world.requests == [{"kind": "inspect", "source": "eats", "query": "North Beach"}]
    events = load_runtime_events(tmp_path)
    assert [event["event_type"] for event in events] == ["information_accessed"]
    assert events[0]["payload"]["source"] == "eats"


def test_missing_information_boundary_fails_closed_and_records_attempt(tmp_path):
    access = InformationAccess(ww_client=object(), memory_dir=tmp_path)

    result = asyncio.run(access(Reach(kind="read", source="files", query="README.md")))

    assert result["accessed"] is False
    assert result["reason"] == "information_access_unavailable"
    events = load_runtime_events(tmp_path)
    assert events[0]["event_type"] == "information_accessed"
    assert events[0]["payload"]["accessed"] is False
