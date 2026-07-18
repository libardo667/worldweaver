from __future__ import annotations

import pytest

from scripts.seed_residents import choose_locations, choose_vocations


def test_fixed_cohort_plan_spreads_vocations_and_prefers_empty_neighborhoods():
    vitality = {
        "busy": {"name": "Busy", "total_agents": 2, "vitality_score": 0.1},
        "quiet_b": {"name": "Quiet B", "total_agents": 0, "vitality_score": 0.5},
        "quiet_a": {"name": "Quiet A", "total_agents": 0, "vitality_score": 0.2},
        "occupied": {"name": "Occupied", "total_agents": 1, "vitality_score": 0.0},
    }

    assert choose_locations(vitality, count=3, explicit=[]) == [
        "Quiet A",
        "Quiet B",
        "Occupied",
    ]
    first = choose_vocations(count=3, seed=27)
    second = choose_vocations(count=3, seed=27)
    assert first == second
    assert len(set(first)) == 3
    assert all("engineering" not in vocation for vocation in first)


def test_fixed_cohort_plan_requires_exact_explicit_locations():
    with pytest.raises(ValueError, match="exactly one distinct"):
        choose_locations({}, count=2, explicit=["One"])
