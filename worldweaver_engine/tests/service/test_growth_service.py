"""Compatibility storage for identity proposals from older resident runners."""

from src.models import ResidentIdentityGrowth
from src.services.growth_service import append_growth_proposals


def _row() -> ResidentIdentityGrowth:
    return ResidentIdentityGrowth(
        actor_id="resident-1",
        growth_text="",
        growth_metadata={},
        growth_proposals=[],
    )


def test_append_growth_proposals_deduplicates_by_pulse_id():
    row = _row()

    first = append_growth_proposals(
        row,
        [
            {"pulse_id": "p1", "body": "first"},
            {"pulse_id": "p2", "body": "second"},
        ],
    )
    second = append_growth_proposals(
        row,
        [
            {"pulse_id": "p2", "body": "duplicate"},
            {"pulse_id": "p3", "body": "third"},
        ],
    )

    assert first == 2
    assert second == 1
    assert [item["pulse_id"] for item in row.growth_proposals] == ["p1", "p2", "p3"]


def test_legacy_promoted_ids_are_not_reintroduced():
    row = _row()
    row.growth_metadata = {"promoted_pulse_ids": ["old-pulse"]}

    added = append_growth_proposals(
        row,
        [{"pulse_id": "old-pulse", "body": "already handled"}],
    )

    assert added == 0
    assert row.growth_proposals == []
