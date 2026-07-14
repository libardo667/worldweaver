from __future__ import annotations

import asyncio

from src.runtime.information import InformationAccess, InformationSource, InformationSourceRegistry, provenance_guidance
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
            "freshness": "stable",
            "locality": "North Beach",
            "visibility": "private",
            "selection_mode": "neighborhood_match",
            "records": [
                {
                    "record_id": "eats:north-beach:bakery",
                    "title": "Corner Bakery",
                    "content": "opens before dawn",
                }
            ],
        }


def test_shared_source_registry_normalizes_provider_records():
    registry = InformationSourceRegistry(
        [
            InformationSource(
                name="artifact",
                description="read one authorized artifact",
                run=lambda query: [{"record_id": "artifact:1", "content": f"read {query}"}],
                provenance="scoped-reading",
                freshness="live",
                locality="hearth",
                selection_mode="exact_path",
            )
        ]
    )

    result = asyncio.run(registry.read("ARTIFACT", "notes.md"))

    assert result["ok"] is True
    assert result["provenance"] == "scoped-reading"
    assert result["records"] == [
        {
            "record_id": "artifact:1",
            "content": "read notes.md",
            "source": "artifact",
            "provenance": "scoped-reading",
            "freshness": "live",
            "locality": "hearth",
            "visibility": "private",
            "selection_mode": "exact_path",
        }
    ]


def test_provenance_guidance_distinguishes_reading_from_knowing():
    reading = provenance_guidance("scoped-reading")
    knowing = provenance_guidance("local-knowledge")

    assert "deliberately read" in reading
    assert "rather than already knowing" in reading
    assert "speak it as your own knowing" in knowing


def test_information_access_is_private_ledger_evidence_not_a_world_act(tmp_path):
    world = _World()
    access = InformationAccess(ww_client=world, memory_dir=tmp_path)

    result = asyncio.run(access(Reach(kind="inspect", source="eats", query="North Beach")))

    assert result["accessed"] is True
    assert "[eats | neighborhood_match | stable] Corner Bakery" in result["detail"]
    assert result["records"][0]["locality"] == "North Beach"
    assert world.requests == [{"kind": "inspect", "source": "eats", "query": "North Beach"}]
    events = load_runtime_events(tmp_path)
    assert [event["event_type"] for event in events] == ["information_accessed"]
    assert events[0]["payload"]["source"] == "eats"
    assert events[0]["payload"]["record_refs"][0]["selection_mode"] == "neighborhood_match"


def test_missing_information_boundary_fails_closed_and_records_attempt(tmp_path):
    access = InformationAccess(ww_client=object(), memory_dir=tmp_path)

    result = asyncio.run(access(Reach(kind="read", source="files", query="README.md")))

    assert result["accessed"] is False
    assert result["reason"] == "information_access_unavailable"
    events = load_runtime_events(tmp_path)
    assert events[0]["event_type"] == "information_accessed"
    assert events[0]["payload"]["accessed"] is False
