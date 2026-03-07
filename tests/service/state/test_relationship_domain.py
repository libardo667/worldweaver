"""Domain isolation tests for RelationshipDomain (Minor 106)."""

from src.services.state.relationships import RelationshipDomain
from src.services.state._types import StateChangeType
from tests.helpers.state_assertions import assert_relationship_parity


class TestRelationshipDomainBasics:
    def test_update_creates_new_relationship(self):
        domain = RelationshipDomain()
        rel, change = domain.update("player", "innkeeper", {"trust": 20})
        assert rel.trust == 20.0
        assert change.change_type == StateChangeType.RELATIONSHIP_CHANGE

    def test_update_clamps_values(self):
        domain = RelationshipDomain()
        rel, _ = domain.update("player", "enemy", {"fear": 200})
        assert rel.fear == 100.0

    def test_alphabetical_key_normalization(self):
        domain = RelationshipDomain()
        domain.update("player", "innkeeper", {"trust": 10})
        # Both orderings should resolve to the same key
        rel_a = domain.get("player", "innkeeper")
        rel_b = domain.get("innkeeper", "player")
        assert rel_a is rel_b

    def test_key_format_is_alphabetical(self):
        domain = RelationshipDomain()
        domain.update("zara", "alex", {"trust": 5})
        assert "alex:zara" in domain.items

    def test_get_missing_returns_none(self):
        domain = RelationshipDomain()
        assert domain.get("a", "b") is None

    def test_disposition_labels(self):
        domain = RelationshipDomain()
        rel, _ = domain.update("player", "friend", {"trust": 90, "respect": 90})
        assert rel.get_overall_disposition() in {"devoted", "friendly", "positive"}

    def test_to_dict_from_dict_roundtrip(self):
        domain = RelationshipDomain()
        domain.update("player", "npc", {"trust": 15, "fear": -5}, memory="helped in fight")
        data = domain.to_dict()
        restored = RelationshipDomain.from_dict(data)
        key = "npc:player"
        assert restored.items[key].trust == 15.0
        assert restored.items[key].memory_fragments == ["helped in fight"]

    def test_items_property_is_same_dict_reference(self):
        domain = RelationshipDomain()
        ref1 = domain.items
        domain.update("a", "b", {"trust": 1})
        ref2 = domain.items
        assert ref1 is ref2

    def test_assert_relationship_parity_helper(self):
        domain = RelationshipDomain()
        domain.update("player", "innkeeper", {"trust": 20.0, "fear": 0.0})
        assert_relationship_parity(domain, {"innkeeper:player": {"trust": 20.0, "fear": 0.0}})
