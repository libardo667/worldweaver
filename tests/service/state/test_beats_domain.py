"""Domain isolation tests for NarrativeBeatsDomain (Minor 106)."""

import pytest

from src.services.state.beats import NarrativeBeatsDomain
from src.models import NarrativeBeat


class TestNarrativeBeatsDomainBasics:
    def test_add_beat_is_active(self):
        domain = NarrativeBeatsDomain()
        domain.add(NarrativeBeat(name="Tension", intensity=0.5, turns_remaining=3))
        assert len(domain.beats) == 1

    def test_add_inactive_beat_ignored(self):
        domain = NarrativeBeatsDomain()
        domain.add(NarrativeBeat(name="Dead", intensity=0.0, turns_remaining=0))
        assert len(domain.beats) == 0

    def test_add_merges_same_name(self):
        domain = NarrativeBeatsDomain()
        domain.add(NarrativeBeat(name="Fear", intensity=0.3, turns_remaining=2))
        domain.add(NarrativeBeat(name="fear", intensity=0.2, turns_remaining=4))
        assert len(domain.beats) == 1
        assert domain.beats[0].intensity == pytest.approx(0.5)
        assert domain.beats[0].turns_remaining == 4

    def test_decay_decrements_turns(self):
        domain = NarrativeBeatsDomain()
        domain.add(NarrativeBeat(name="Mystery", intensity=1.0, turns_remaining=2, decay=0.8))
        domain.decay()
        assert domain.beats[0].turns_remaining == 1

    def test_decay_removes_expired_beats(self):
        domain = NarrativeBeatsDomain()
        domain.add(NarrativeBeat(name="Flash", intensity=0.1, turns_remaining=1, decay=0.0))
        domain.decay()
        assert len(domain.beats) == 0

    def test_get_active_filters_expired(self):
        domain = NarrativeBeatsDomain()
        domain.add(NarrativeBeat(name="Active", intensity=0.5, turns_remaining=3))
        domain.add(NarrativeBeat(name="Gone", intensity=0.0, turns_remaining=0))
        active = domain.get_active()
        assert len(active) == 1
        assert active[0].name == "Active"

    def test_to_dict_omits_inactive(self):
        domain = NarrativeBeatsDomain()
        domain.add(NarrativeBeat(name="Live", intensity=0.4, turns_remaining=2))
        data = domain.to_dict()
        assert len(data) == 1
        assert data[0]["name"] == "Live"

    def test_from_dict_roundtrip(self):
        domain = NarrativeBeatsDomain()
        domain.add(NarrativeBeat(name="Tension", intensity=0.6, turns_remaining=3, decay=0.7))
        data = domain.to_dict()
        restored = NarrativeBeatsDomain.from_dict(data)
        assert len(restored.beats) == 1
        assert restored.beats[0].name == "Tension"
        assert restored.beats[0].intensity == pytest.approx(0.6)

    def test_from_dict_skips_invalid_entries(self):
        domain = NarrativeBeatsDomain.from_dict(["not-a-dict", None, {"name": "Good", "intensity": 0.5, "turns_remaining": 2, "decay": 0.7, "vector": None, "source": "system"}])
        assert len(domain.beats) == 1
