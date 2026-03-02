"""Tests for src/services/state_manager.py."""

import math

from src.services.state_manager import (
    AdvancedStateManager,
    EnvironmentalState,
    ItemState,
    RelationshipState,
)


class TestAdvancedStateManager:

    def _make(self, sid="test-session"):
        return AdvancedStateManager(sid)

    # -- Variables --

    def test_set_get_variable_roundtrip(self):
        sm = self._make()
        sm.set_variable("gold", 42)
        assert sm.get_variable("gold") == 42

    def test_get_variable_default(self):
        sm = self._make()
        assert sm.get_variable("missing", "default") == "default"

    def test_increment_from_zero(self):
        sm = self._make()
        assert sm.increment_variable("gold", 5) == 5

    def test_increment_existing(self):
        sm = self._make()
        sm.set_variable("gold", 10)
        assert sm.increment_variable("gold", 3) == 13

    # -- Inventory --

    def test_add_item_new(self):
        sm = self._make()
        item = sm.add_item("sword", "Iron Sword", quantity=1, properties={"damage": 10})
        assert item.name == "Iron Sword"
        assert item.quantity == 1
        assert item.properties["damage"] == 10

    def test_add_item_increases_quantity(self):
        sm = self._make()
        sm.add_item("arrow", "Arrow", quantity=5)
        sm.add_item("arrow", "Arrow", quantity=3)
        assert sm.inventory["arrow"].quantity == 8

    def test_remove_item_decrements(self):
        sm = self._make()
        sm.add_item("potion", "Healing Potion", quantity=3)
        assert sm.remove_item("potion", 1) is True
        assert sm.inventory["potion"].quantity == 2

    def test_remove_item_at_zero_deletes(self):
        sm = self._make()
        sm.add_item("key", "Rusty Key", quantity=1)
        sm.remove_item("key", 1)
        assert "key" not in sm.inventory

    def test_remove_nonexistent_returns_false(self):
        sm = self._make()
        assert sm.remove_item("nothing") is False

    # -- Relationships --

    def test_update_relationship_creates_new(self):
        sm = self._make()
        rel = sm.update_relationship("player", "npc1", {"trust": 20})
        assert rel.trust == 20
        assert rel.interaction_count == 1

    def test_relationship_clamped_to_range(self):
        sm = self._make()
        rel = sm.update_relationship("player", "npc1", {"trust": 200})
        assert rel.trust == 100  # clamped

    def test_relationship_disposition_labels(self):
        sm = self._make()
        sm.update_relationship("player", "npc1", {"trust": 80, "respect": 80})
        rel = sm.get_relationship("player", "npc1")
        assert rel.get_overall_disposition() in ("devoted", "friendly", "positive")

    def test_relationship_memory(self):
        sm = self._make()
        sm.update_relationship("player", "npc1", {"trust": 5}, memory="Helped me")
        rel = sm.get_relationship("player", "npc1")
        assert "Helped me" in rel.memory_fragments

    # -- Environment --

    def test_update_environment(self):
        sm = self._make()
        sm.update_environment({"weather": "stormy", "time_of_day": "night"})
        assert sm.environment.weather == "stormy"
        assert sm.environment.time_of_day == "night"

    def test_mood_modifiers(self):
        env = EnvironmentalState(weather="rainy", time_of_day="night")
        modifiers = env.get_mood_modifier()
        assert "melancholy" in modifiers
        assert "fear" in modifiers

    def test_apply_world_delta(self):
        sm = self._make()
        applied = sm.apply_world_delta(
            {
                "bridge_broken": True,
                "environment": {"weather": "stormy"},
                "spatial_nodes": {"bridge": {"status": "destroyed"}},
            }
        )
        assert sm.get_variable("bridge_broken") is True
        assert sm.environment.weather == "stormy"
        spatial = sm.get_variable("spatial_nodes", {})
        assert spatial["bridge"]["status"] == "destroyed"
        assert applied["variables"]["bridge_broken"] is True

    def test_narrative_beats_stack_and_decay(self):
        sm = self._make()
        sm.add_narrative_beat(
            {
                "name": "IncreasingTension",
                "intensity": 0.8,
                "turns_remaining": 3,
                "decay": 0.5,
            }
        )
        sm.add_narrative_beat(
            {
                "name": "Catharsis",
                "intensity": 0.4,
                "turns_remaining": 2,
                "decay": 0.5,
            }
        )

        active = sm.get_active_narrative_beats()
        assert len(active) == 2

        sm.decay_narrative_beats()
        active = sm.get_active_narrative_beats()
        beat_by_name = {beat.name: beat for beat in active}
        assert beat_by_name["IncreasingTension"].turns_remaining == 2
        assert math.isclose(beat_by_name["IncreasingTension"].intensity, 0.4, rel_tol=1e-9)
        assert beat_by_name["Catharsis"].turns_remaining == 1
        assert math.isclose(beat_by_name["Catharsis"].intensity, 0.2, rel_tol=1e-9)

        sm.decay_narrative_beats()
        active = sm.get_active_narrative_beats()
        assert len(active) == 1
        assert active[0].name == "IncreasingTension"

        sm.decay_narrative_beats()
        assert sm.get_active_narrative_beats() == []

    # -- Export / Import --

    def test_export_import_roundtrip(self):
        sm = self._make()
        sm.set_variable("gold", 50)
        sm.add_item("gem", "Ruby", quantity=2)
        sm.update_relationship("player", "npc1", {"trust": 30})
        sm.update_environment({"weather": "snowy"})
        sm.add_narrative_beat(
            {
                "name": "IncreasingTension",
                "intensity": 0.5,
                "turns_remaining": 3,
                "decay": 0.65,
            }
        )

        exported = sm.export_state()
        assert exported["_v"] == 2

        sm2 = self._make("new-session")
        sm2.import_state(exported)
        assert sm2.get_variable("gold") == 50
        assert sm2.inventory["gem"].quantity == 2
        assert sm2.get_relationship("player", "npc1").trust == 30
        assert sm2.environment.weather == "snowy"
        assert sm2.get_active_narrative_beats()[0].name == "IncreasingTension"

    # -- Change history --

    def test_change_history_tracked(self):
        sm = self._make()
        sm.set_variable("x", 1)
        sm.set_variable("x", 2)
        assert len(sm.change_history) == 2
        assert sm.change_history[0].old_value is None
        assert sm.change_history[1].old_value == 1


class TestRelationshipState:

    def test_disposition_enemy(self):
        rel = RelationshipState("a", "b", trust=-50, fear=60, respect=-50)
        assert rel.get_overall_disposition() == "enemy"

    def test_disposition_neutral(self):
        rel = RelationshipState("a", "b")
        assert rel.get_overall_disposition() == "neutral"


class TestItemState:

    def test_can_combine_with(self):
        sword = ItemState(id="sword", name="Sword", properties={"combinable_with": ["gem"]})
        gem = ItemState(id="gem", name="Gem")
        assert sword.can_combine_with(gem) is True
        assert gem.can_combine_with(sword) is False

    def test_get_available_actions(self):
        potion = ItemState(id="potion", name="Potion", properties={"consumable": True})
        actions = potion.get_available_actions({"location": "tavern"})
        assert "use" in actions
        assert "examine" in actions
