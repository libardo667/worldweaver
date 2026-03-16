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

    def test_set_get_world_context_roundtrip(self):
        sm = self._make()
        context = {
            "world_name": "San Francisco",
            "city_id": "san_francisco",
            "canonical_locations": ["The Mission", "Chinatown"],
        }
        sm.set_world_context(context)
        assert sm.get_world_context() == context

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

    def test_goal_state_roundtrip_and_timeline(self):
        sm = self._make()
        sm.set_goal_state(
            primary_goal="Deliver medicine to the ridge village",
            subgoals=["Cross the river", "Find a guide"],
            urgency=0.7,
            complication=0.2,
            note="Initial objective",
            source="test",
        )
        sm.mark_goal_milestone(
            "Bandits blocked the road",
            status="complicated",
            complication_delta=0.3,
            source="test",
        )
        summary = sm.get_state_summary()
        assert summary["goal"]["primary_goal"] == "Deliver medicine to the ridge village"
        assert summary["goal"]["urgency"] == 0.7
        assert summary["goal"]["complication"] == 0.5
        assert summary["arc_timeline"]
        assert summary["arc_timeline"][0]["status"] == "complicated"

    def test_apply_goal_update_branches_subgoal(self):
        sm = self._make()
        sm.set_goal_state(primary_goal="Find the missing scout", source="test")
        sm.apply_goal_update(
            {
                "status": "branched",
                "milestone": "Chased a rumor toward the marsh",
                "subgoal": "Question the ferryman",
                "urgency_delta": 0.1,
                "complication_delta": 0.2,
            },
            source="test",
        )
        assert "Question the ferryman" in sm.goal_state.subgoals
        assert sm.goal_state.urgency == 0.1
        assert sm.goal_state.complication == 0.2

    def test_backfill_primary_goal_after_initial_turn_is_deterministic_and_idempotent(self):
        sm = self._make()
        sm.set_variable("player_role", "exiled cartographer")
        sm.set_world_bible(
            {
                "central_tension": "A fragile city-state teeters on the edge of collapse.",
            }
        )
        sm.advance_story_arc()  # turn_count -> 1

        first = sm.backfill_primary_goal_if_empty_after_initial_turn()
        second = sm.backfill_primary_goal_if_empty_after_initial_turn()
        goal_state = sm.get_goal_state()
        timeline = sm.get_arc_timeline(limit=5)

        assert first["applied"] is True
        assert second["applied"] is False
        assert second["reason"] == "primary_goal_present"
        assert goal_state["primary_goal"]
        assert "exiled cartographer" in goal_state["primary_goal"].lower()
        assert len(timeline) == 1
        assert timeline[0]["source"] == "system_goal_backfill"

    def test_backfill_primary_goal_noop_before_initial_turn(self):
        sm = self._make()
        sm.set_variable("player_role", "courier")
        outcome = sm.backfill_primary_goal_if_empty_after_initial_turn()
        assert outcome["applied"] is False
        assert outcome["reason"] == "below_turn_threshold"
        assert sm.get_goal_state()["primary_goal"] == ""

    def test_structured_state_defaults_exist(self):
        sm = self._make()
        assert sm.get_variable("stance") == "observing"
        assert sm.get_variable("focus") == ""
        assert sm.get_variable("tactics") == []
        assert sm.get_variable("injury_state") == "healthy"
        assert sm.get_variable("state.unstructured") == {}
        assert sm.get_variable("state.recent_motifs") == []

    def test_motif_ledger_extract_append_and_bound(self):
        sm = self._make()
        motifs = sm.extract_motifs_from_text(
            "Neon rain hisses over copper gutters while drones hum in static rain.",
            max_items=6,
        )
        assert motifs
        sm.append_recent_motifs(motifs, max_items=5)
        sm.append_recent_motifs(["ozone", "neon", "copper"], max_items=5)
        recent = sm.get_recent_motifs(limit=5)
        assert len(recent) <= 5
        assert "neon" in recent

    def test_decay_tactics_expires_entries(self):
        sm = self._make()
        sm.set_variable(
            "tactics",
            [
                {"name": "decoy_active", "ttl": 2},
                {"name": "smoke_bomb", "ttl": 1},
            ],
        )
        expired = sm.decay_tactics()
        assert expired == ["smoke_bomb"]
        assert sm.get_variable("tactics") == [{"name": "decoy_active", "ttl": 1}]

    # -- Export / Import --

    def test_export_import_roundtrip(self):
        sm = self._make()
        sm.set_variable("gold", 50)
        sm.add_item("gem", "Ruby", quantity=2)
        sm.update_relationship("player", "npc1", {"trust": 30})
        sm.update_environment({"weather": "snowy"})
        sm.set_goal_state(
            primary_goal="Secure safe passage",
            subgoals=["Negotiate with caravan leader"],
            urgency=0.6,
            complication=0.3,
            source="test",
        )
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
        assert sm2.goal_state.primary_goal == "Secure safe passage"
        assert sm2.goal_state.subgoals == ["Negotiate with caravan leader"]
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


class TestOrchestratorDomainDelegation:
    """Verify that AdvancedStateManager correctly delegates to typed domain objects."""

    def test_add_item_appends_to_change_history(self):
        sm = AdvancedStateManager("test")
        sm.add_item("key", "Rusty Key")
        variables = {c.variable for c in sm.change_history}
        assert "inventory.key" in variables

    def test_remove_item_appends_to_change_history(self):
        sm = AdvancedStateManager("test")
        sm.add_item("coin", "Gold Coin", quantity=5)
        # Clear history to isolate remove change
        sm.change_history.clear()
        sm.remove_item("coin", quantity=3)
        variables = {c.variable for c in sm.change_history}
        assert "inventory.coin" in variables

    def test_update_relationship_appends_to_change_history(self):
        sm = AdvancedStateManager("test")
        sm.update_relationship("player", "npc", {"trust": 10})
        variables = {c.variable for c in sm.change_history}
        assert any("relationship" in v for v in variables)

    def test_domain_properties_reflect_mutations(self):
        sm = AdvancedStateManager("test")
        sm.add_item("sword", "Iron Sword", quantity=2)
        assert sm.inventory["sword"].quantity == 2
        assert sm._inventory.items["sword"].quantity == 2
        # Both are the same dict
        assert sm.inventory is sm._inventory.items

    def test_goal_state_property_reflects_domain(self):
        sm = AdvancedStateManager("test")
        sm.set_goal_state(primary_goal="Defeat the dragon")
        assert sm.goal_state.primary_goal == "Defeat the dragon"
        assert sm._goals.state.primary_goal == "Defeat the dragon"
        assert sm.goal_state is sm._goals.state

    def test_active_narrative_beats_property_reflects_domain(self):
        from src.models import NarrativeBeat

        sm = AdvancedStateManager("test")
        sm.add_narrative_beat(NarrativeBeat(name="Tension", intensity=0.5, turns_remaining=3))
        assert len(sm.active_narrative_beats) == 1
        assert sm.active_narrative_beats is sm._beats.beats

    def test_fork_shares_domain_references(self):
        sm = AdvancedStateManager("test")
        sm.add_item("map", "Treasure Map")
        fork = sm.fork_for_projection()
        assert fork._inventory is sm._inventory
        assert fork._relationships is sm._relationships
        assert fork._goals is sm._goals
        assert fork._beats is sm._beats
        # Variables are copied, not shared
        assert fork.variables is not sm.variables

    def test_import_state_rebuilds_all_domains(self):
        from tests.helpers.state_assertions import assert_export_import_roundtrip

        sm = AdvancedStateManager("test")
        sm.add_item("torch", "Torch", quantity=3)
        sm.update_relationship("player", "guard", {"respect": 15})
        sm.set_goal_state(primary_goal="Survive the night", urgency=0.6)
        assert_export_import_roundtrip(sm)
